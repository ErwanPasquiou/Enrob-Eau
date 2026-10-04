"""Migration explicite CODEX-001 des JSON locaux, application arrêtée."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from services import business_data_service as data
from services import dossier_edit_service as edits
from services.data_model import SCHEMAS


def adapt_store(source):
    """Préserve les valeurs et les liens ; refuse un mélange de versions."""
    target = deepcopy(source)
    versions = set()
    for table in ("interventions", "prestations"):
        if not isinstance(target[table], list):
            raise ValueError(f"{table} : une liste de lignes est attendue.")
        legacy_fields = {f.replace("WorkOrderReferenceEnrobEau", "WorkOrderReference")
                         for f in SCHEMAS[table] if f != "WorkOrderReferenceSaur"}
        for index, row in enumerate(target[table], 1):
            if not isinstance(row, dict):
                raise ValueError(f"{table}, ligne {index} : objet attendu.")
            if set(row) == legacy_fields:
                versions.add("legacy")
                reference = row.pop("WorkOrderReference")
                row["WorkOrderReferenceEnrobEau"] = reference
                if table == "interventions":
                    row["WorkOrderReferenceSaur"] = reference
            elif set(row) == set(SCHEMAS[table]):
                versions.add("target")
            else:
                raise ValueError(f"{table}, ligne {index} : colonnes inconnues ou migration partielle.")
    if len(versions) > 1:
        raise ValueError("Modèles ancien et nouveau mélangés : vérifiez les fichiers avant migration.")
    data.validate_store(target)
    # L'ordre des colonnes suit le schéma ; aucune valeur métier n'est recalculée.
    return {table: [{field: row[field] for field in SCHEMAS[table]} for row in rows]
            for table, rows in target.items()}


def migrate_local_data(apply=False):
    """Valide, sauvegarde puis écrit les seules tables modifiées. Idempotent."""
    with data.LOCK:
        originals = {table: (data.DATA_DIR / f"{table}.json").read_bytes() for table in SCHEMAS}
        before = {table: json.loads(content.decode("utf-8-sig")) for table, content in originals.items()}
        after = adapt_store(before)
        changed = [table for table in SCHEMAS if before[table] != after[table]]
        result = dict(changed=changed, counts={table: len(rows) for table, rows in after.items()}, backup=None)
        if not apply or not changed:
            return result
        backup = data.DATA_DIR / "backups" / datetime.now().strftime("CODEX-001-%Y%m%d-%H%M%S-%f")
        backup.mkdir(parents=True, exist_ok=False)
        for table, content in originals.items():
            (backup / f"{table}.json").write_bytes(content)
        # Refuse une édition extérieure survenue pendant la préparation.
        if any((data.DATA_DIR / f"{table}.json").read_bytes() != content for table, content in originals.items()):
            raise ValueError("Les fichiers ont changé pendant la migration. Aucune écriture effectuée.")
        try:
            edits._persist_changes(before, after)
        except (ValueError, OSError) as exc:
            raise OSError(f"Échec de migration ; sauvegarde des originaux : {backup}. Vérifiez/restaurez les trois JSON avant de redémarrer.") from exc
        result["backup"] = str(backup)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Sauvegarder et migrer ; sans cette option, vérifier seulement.")
    parser.add_argument("--data-dir", type=Path, default=data.DATA_DIR, help="Dossier contenant les trois JSON locaux.")
    args = parser.parse_args()
    data.DATA_DIR = args.data_dir.resolve()
    try:
        result = migrate_local_data(apply=args.apply)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Migration refusée : {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
