"""Photos du prototype en BLOB SQLite. Aucune lecture globale des binaires."""
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sqlite3
import warnings
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from services import business_data_service as data

TABLES = {"demandes": ("PhotoDemande", "RequestReference"),
          "prestations": ("PhotoPrestation", "ServiceReference")}
METADATA = "PhotoReference, PhotoName, FileName, MimeType, SizeBytes, Caption, CreatedBy, CreatedAt, UpdatedAt, Version"
MAX_BYTES = 15 * 1024 * 1024
MAX_BATCH = 20


@contextmanager
def connection():
    from services.reference_service import ensure_ready
    ensure_ready()
    db = sqlite3.connect(data.DATA_DIR / "photos.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.executescript((Path(__file__).resolve().parents[1] / "data/photos.sql").read_text(encoding="utf-8"))
        with db:
            for name, _ in TABLES.values():
                if "PhotoName" not in {r["name"] for r in db.execute(f"PRAGMA table_info({name})")}:
                    db.execute(f"ALTER TABLE {name} ADD COLUMN PhotoName TEXT NOT NULL DEFAULT ''")
                    db.execute(f"UPDATE {name} SET PhotoName = FileName")
            yield db
    except sqlite3.Error as exc:
        raise OSError("Le stockage des photos est indisponible. Réessayez.") from exc
    finally:
        db.close()


def check_parent(table, reference, owner_email=None):
    if table not in TABLES:
        raise ValueError("Type de photo invalide.")
    key = TABLES[table][1]
    row = next((r for r in data.load_store()[table] if r[key] == reference), None)
    if row is None:
        raise ValueError("La demande ou la prestation n'existe plus.")
    if owner_email is not None:
        if table != "demandes" or not owner_email.strip() or str(row["RequesterReference"] or "").strip().casefold() != owner_email.strip().casefold():
            raise ValueError("Vous ne pouvez consulter ou modifier que vos propres demandes.")


def prepare_photo(name, content, caption="", photo_name=None):
    if not photo_name or not photo_name.strip():
        raise ValueError("Donnez un nom à chaque photo avant d'enregistrer.")
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Chaque photo doit contenir entre 1 octet et 15 Mo.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as picture:
                fmt = picture.format
                if fmt not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Formats acceptés : JPEG, PNG et WebP.")
                picture.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Le fichier n'est pas une photo valide ou ses dimensions sont trop grandes.") from exc
    return dict(PhotoName=photo_name.strip(), FileName=Path(name.replace("\\", "/")).name or "photo", Content=bytes(content),
                MimeType={"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt],
                SizeBytes=len(content), Caption=caption.strip())


def list_photos(table, reference, owner_email=None):
    check_parent(table, reference, owner_email)
    name, key = TABLES[table]
    with connection() as db:
        return [dict(r) for r in db.execute(f"SELECT {METADATA} FROM {name} WHERE {key} = ? ORDER BY CreatedAt, PhotoReference", (reference,))]


def read_photo(table, reference, photo_id, owner_email=None):
    check_parent(table, reference, owner_email)
    name, key = TABLES[table]
    with connection() as db:
        row = db.execute(f"SELECT Content FROM {name} WHERE {key} = ? AND PhotoReference = ?", (reference, photo_id)).fetchone()
    if row is None:
        raise ValueError("Cette photo n'existe plus. Actualisez la liste.")
    return row["Content"]


def add_photos(table, reference, photos, actor, owner_email=None):
    from services.dossier_edit_service import LOCK
    if len(photos) > MAX_BATCH:
        raise ValueError("Ajoutez au maximum 20 photos à la fois.")
    checked = [prepare_photo(p["FileName"], p["Content"], p.get("Caption", ""), p.get("PhotoName")) for p in photos]
    with LOCK:
        check_parent(table, reference, owner_email)
        name, key = TABLES[table]
        with connection() as db:
            for photo in checked:
                now = datetime.now().isoformat(timespec="microseconds")
                db.execute(f"INSERT INTO {name} (PhotoReference, {key}, PhotoName, FileName, MimeType, SizeBytes, Content, Caption, CreatedBy, CreatedAt, UpdatedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (uuid4().hex, reference, photo["PhotoName"], photo["FileName"], photo["MimeType"], photo["SizeBytes"], photo["Content"], photo["Caption"], actor, now, now))


def update_photo(table, reference, original, caption, replacement=None, owner_email=None, photo_name=None):
    from services.dossier_edit_service import LOCK
    title = original["PhotoName"] if photo_name is None else photo_name.strip()
    if not title:
        raise ValueError("Le nom de la photo est obligatoire.")
    photo = prepare_photo(replacement["FileName"], replacement["Content"], caption, title) if replacement else None
    with LOCK:
        check_parent(table, reference, owner_email)
        name, key = TABLES[table]
        values = [title, caption.strip(), datetime.now().isoformat(timespec="microseconds")]
        assignments = "PhotoName = ?, Caption = ?, UpdatedAt = ?, Version = Version + 1"
        if photo:
            assignments += ", FileName = ?, MimeType = ?, SizeBytes = ?, Content = ?"
            values.extend(photo[f] for f in ("FileName", "MimeType", "SizeBytes", "Content"))
        with connection() as db:
            result = db.execute(f"UPDATE {name} SET {assignments} WHERE {key} = ? AND PhotoReference = ? AND Version = ?",
                                (*values, reference, original["PhotoReference"], original["Version"]))
            if result.rowcount != 1:
                raise ValueError("La photo a changé ou a été supprimée. Actualisez la liste.")


def delete_photo(table, reference, original, owner_email=None):
    from services.dossier_edit_service import LOCK
    with LOCK:
        check_parent(table, reference, owner_email)
        name, key = TABLES[table]
        with connection() as db:
            result = db.execute(f"DELETE FROM {name} WHERE {key} = ? AND PhotoReference = ? AND Version = ?",
                                (reference, original["PhotoReference"], original["Version"]))
            if result.rowcount != 1:
                raise ValueError("La photo a changé ou a été supprimée. Actualisez la liste.")
