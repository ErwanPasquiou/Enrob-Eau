"""CODEX-002 : normalisation locale des références, application arrêtée."""
import argparse
from contextlib import closing
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from services import business_data_service as data
from services import dossier_edit_service as edits
from services.data_model import SCHEMAS
from services.reference_service import (
    PREFIXES, MAX_NUMBER, PENDING_FILE, ensure_ready, read_sequences, reference_number,
)

JSON_FILES = [f"{table}.json" for table in SCHEMAS]
FILES = [*JSON_FILES, "sequences.json", "photos.sqlite3"]
PHOTO_LINKS = {"PhotoDemande": ("demandes", "RequestReference"),
               "PhotoPrestation": ("prestations", "ServiceReference")}


def plan_references(source, counters):
    """Conserve les références conformes et réserve au-delà des maxima connus."""
    data.validate_store(source)
    target = deepcopy(source)
    counters = counters.copy()
    mappings = {}
    for table, rows in source.items():
        key = SCHEMAS[table][0]
        counters[table] = max([counters[table], *[reference_number(table, r[key]) or 0 for r in rows]])
        mappings[table] = {}
        for row in rows:
            old = row[key]
            if reference_number(table, old) is not None:
                new = old
            else:
                if counters[table] >= MAX_NUMBER:
                    raise ValueError(f"Séquence {PREFIXES[table]} épuisée ; migration impossible sur six chiffres.")
                counters[table] += 1
                new = f"{PREFIXES[table]}-{counters[table]:06d}"
            mappings[table][old] = new
        for row in target[table]:
            row[key] = mappings[table][row[key]]
    for row in target["interventions"]:
        row["RequestReference"] = mappings["demandes"][row["RequestReference"]]
    for row in target["prestations"]:
        row["WorkOrderReferenceEnrobEau"] = mappings["interventions"][row["WorkOrderReferenceEnrobEau"]]
    data.validate_store(target, normalized=True)
    return target, counters, mappings


def _photo_connection(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def audit_photos(path, mappings):
    """Ne lit pas les BLOB ; refuse des liens orphelins ou une base ambiguë."""
    if not path.exists():
        return {}
    if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("La base photos possède un journal actif. Fermez les connexions et consolidez SQLite avant migration.")
    counts = {}
    with closing(_photo_connection(path)) as db:
        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
            raise ValueError("La migration photos nécessite le mode SQLite DELETE utilisé par le prototype.")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("La base photos est endommagée.")
        for photo_table, (table, key) in PHOTO_LINKS.items():
            counts[photo_table] = 0
            for reference, count in db.execute(f"SELECT {key}, COUNT(*) FROM {photo_table} GROUP BY {key}"):
                if reference not in mappings[table]:
                    raise ValueError(f"{photo_table} : parent inexistant {reference}. Migration refusée.")
                counts[photo_table] += count
    return counts


def _digest(path):
    if not path.exists():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _replace_file(source, destination):
    """Publication/restauration atomique d'un fichier, y compris SQLite."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            with source.open("rb") as original:
                shutil.copyfileobj(original, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def recover_migration():
    """Restaure le jeu complet après échec/interruption ; peut être relancé."""
    with data.LOCK:
        marker = data.DATA_DIR / PENDING_FILE
        if not marker.exists():
            return None
        journal = json.loads(marker.read_text(encoding="utf-8"))
        backup = Path(journal["backup"]).resolve()
        if not backup.is_relative_to((data.DATA_DIR / "backups").resolve()):
            raise ValueError("Chemin de sauvegarde de migration invalide.")
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        if set(manifest) != set(FILES):
            raise ValueError("Manifest de sauvegarde incomplet.")
        for name, digest in manifest.items():
            if name in JSON_FILES and digest is None:
                raise ValueError("Sauvegarde métier incomplète.")
            if digest is not None and _digest(backup / name) != digest:
                raise ValueError(f"Sauvegarde altérée : {name}. Récupération refusée.")
        for name, digest in manifest.items():
            destination = data.DATA_DIR / name
            if digest is not None:
                _replace_file(backup / name, destination)
            elif destination.exists():
                destination.unlink()
        marker.unlink()
        return str(backup)


def migrate_references(apply=False):
    with data.LOCK:
        ensure_ready()
        manifest = {name: _digest(data.DATA_DIR / name) for name in FILES}
        source = {table: json.loads((data.DATA_DIR / f"{table}.json").read_text(encoding="utf-8-sig")) for table in SCHEMAS}
        previous_counters = read_sequences()
        target, counters, mappings = plan_references(source, previous_counters)
        photos = audit_photos(data.DATA_DIR / "photos.sqlite3", mappings)
        changes = {table: sum(old != new for old, new in mapping.items()) for table, mapping in mappings.items()}
        result = dict(changes=changes, counters=counters, photos=photos, backup=None)
        if not apply or (not any(changes.values()) and counters == previous_counters and manifest["sequences.json"] is not None):
            return result
        backup = data.DATA_DIR / "backups" / datetime.now().strftime("CODEX-002-%Y%m%d-%H%M%S-%f")
        prepared = backup / "prepared"
        prepared.mkdir(parents=True, exist_ok=False)
        for name, digest in manifest.items():
            if digest is not None:
                shutil.copyfile(data.DATA_DIR / name, backup / name)
        (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (backup / "references.json").write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding="utf-8")
        for table, rows in target.items():
            (prepared / f"{table}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        (prepared / "sequences.json").write_text(json.dumps(counters, indent=2), encoding="utf-8")
        publish = [*JSON_FILES, "sequences.json"]
        if manifest["photos.sqlite3"] is not None:
            staged_db = prepared / "photos.sqlite3"
            shutil.copyfile(backup / "photos.sqlite3", staged_db)
            with closing(sqlite3.connect(staged_db)) as db, db:
                for photo_table, (table, key) in PHOTO_LINKS.items():
                    for old, new in mappings[table].items():
                        if old != new:
                            db.execute(f"UPDATE {photo_table} SET {key} = ? WHERE {key} = ?", (new, old))
            audit_photos(staged_db, {table: {new: new for new in mapping.values()} for table, mapping in mappings.items()})
            publish.append("photos.sqlite3")
        if any(_digest(data.DATA_DIR / name) != digest or
               (digest is not None and _digest(backup / name) != digest) for name, digest in manifest.items()):
            raise ValueError("Les fichiers ont changé pendant la préparation. Aucune migration publiée.")
        # Le marqueur reste présent si le processus est interrompu : aucun écran
        # ne peut alors lire le mélange transitoire de versions.
        edits._write_table("reference_migration_pending", {"backup": str(backup.resolve())})
        try:
            for name in publish:
                _replace_file(prepared / name, data.DATA_DIR / name)
        except Exception:
            recover_migration()
            raise
        (data.DATA_DIR / PENDING_FILE).unlink()
        result["backup"] = str(backup)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="Sauvegarder et publier le jeu normalisé.")
    action.add_argument("--recover", action="store_true", help="Restaurer les originaux après une migration interrompue.")
    parser.add_argument("--data-dir", type=Path, default=data.DATA_DIR)
    args = parser.parse_args()
    data.DATA_DIR = args.data_dir.resolve()
    try:
        result = {"restored": recover_migration()} if args.recover else migrate_references(args.apply)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Migration CODEX-002 refusée : {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
