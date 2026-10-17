"""Paramètres des suivis, persistés localement et séparés par mode."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from uuid import uuid4

from services.auth_service import require_admin
from services.cost_monitoring_service import validate_resource


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data/exemples/finops.sqlite3"
DEMO_DEFAULTS = [
    dict(name="Enrob’Eau · serveur démo", kind="serveur", external_id="DEMO-SERVER-01", rate="1", shared=False),
    dict(name="SQL partagé · compute démo", kind="compute", external_id="DEMO-COMPUTE-01", rate="0.9", shared=True),
]


@contextmanager
def _connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(DATABASE_PATH, timeout=15)) as db:
            db.row_factory = sqlite3.Row
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS finops_resources (
                    id TEXT PRIMARY KEY, mode TEXT NOT NULL, name TEXT NOT NULL,
                    kind TEXT NOT NULL, external_id TEXT NOT NULL, rate TEXT NOT NULL,
                    shared INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(mode, kind, external_id))""")
                db.execute("CREATE TABLE IF NOT EXISTS finops_initialized (mode TEXT PRIMARY KEY)")
                yield db
    except sqlite3.IntegrityError as exc:
        raise ValueError("Cet identifiant est déjà suivi pour ce type de ressource et cette source.") from exc
    except sqlite3.Error as exc:
        raise OSError("Impossible d’enregistrer ou de lire les suivis locaux.") from exc


def _check_mode(mode):
    if mode not in ("demo", "live"):
        raise ValueError("Source de données inconnue.")


def _insert(db, mode, resource):
    resource_id = str(uuid4())
    db.execute("INSERT INTO finops_resources (id,mode,name,kind,external_id,rate,shared) VALUES (?,?,?,?,?,?,?)",
               (resource_id, mode, resource["name"], resource["kind"], resource["external_id"], resource["rate"], int(resource["shared"])))
    return resource_id


def list_resources(mode, defaults=()):
    require_admin()
    _check_mode(mode)
    with _connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM finops_initialized WHERE mode=?", (mode,)).fetchone():
            for resource in DEMO_DEFAULTS if mode == "demo" else defaults:
                _insert(db, mode, validate_resource(resource))
            db.execute("INSERT INTO finops_initialized (mode) VALUES (?)", (mode,))
        return [dict(row) for row in db.execute("SELECT * FROM finops_resources WHERE mode=? ORDER BY kind DESC,name,id", (mode,))]


def save_resource(mode, values, resource_id=None, expected_version=None):
    require_admin()
    _check_mode(mode)
    resource = validate_resource(values)
    with _connection() as db:
        if resource_id is None:
            return _insert(db, mode, resource)
        row = db.execute("SELECT kind FROM finops_resources WHERE id=? AND mode=?", (resource_id, mode)).fetchone()
        if row is None:
            raise ValueError("Ce suivi n’existe plus. Actualisez la page.")
        if row["kind"] != resource["kind"]:
            raise ValueError("Le type du suivi ne peut pas être changé ; ajoutez une autre ressource.")
        cursor = db.execute("""UPDATE finops_resources SET name=?,external_id=?,rate=?,shared=?,version=version+1
                               WHERE id=? AND mode=? AND version=?""",
                            (resource["name"], resource["external_id"], resource["rate"], int(resource["shared"]), resource_id, mode, expected_version))
        if cursor.rowcount != 1:
            raise ValueError("Ce suivi a été modifié ailleurs. Fermez puis rouvrez la fenêtre.")
        return resource_id
