"""Séquences locales persistantes, réservées sous le verrou du prototype."""
import json
import re

from services import business_data_service as data
from services.data_model import SCHEMAS

PREFIXES = {"demandes": "DEM", "interventions": "INT", "prestations": "PR"}
MAX_NUMBER = 999999
PENDING_FILE = "reference_migration_pending.json"


def ensure_ready():
    if (data.DATA_DIR / PENDING_FILE).exists():
        raise ValueError("Migration CODEX-002 interrompue ou en cours. Application arrêtée, exécutez la récupération --recover (voir README).")


def reference_number(table, reference):
    if isinstance(reference, str) and re.fullmatch(rf"{PREFIXES[table]}-[0-9]{{6}}", reference):
        number = int(reference.rsplit("-", 1)[1])
        if number > 0:
            return number
    return None


def validate_reference(table, reference):
    if reference_number(table, reference) is None:
        raise ValueError(f"Référence {table} invalide : format {PREFIXES[table]}-000001 attendu. Migrez les anciennes références avec CODEX-002.")


def read_sequences():
    path = data.DATA_DIR / "sequences.json"
    if not path.exists():
        return dict.fromkeys(PREFIXES, 0)
    counters = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(counters, dict) or set(counters) != set(PREFIXES)
            or any(type(v) is not int or not 0 <= v <= MAX_NUMBER for v in counters.values())):
        raise ValueError("Compteurs locaux invalides : restaurez sequences.json depuis une sauvegarde cohérente.")
    return counters


def advance_sequences(store):
    """Conserve le maximum historique et absorbe les références importées."""
    with data.LOCK:
        ensure_ready()
        counters = read_sequences()
        previous = counters.copy()
        for table, rows in store.items():
            for row in rows:
                reference = row[SCHEMAS[table][0]]
                validate_reference(table, reference)
                counters[table] = max(counters[table], reference_number(table, reference))
        if counters != previous or not (data.DATA_DIR / "sequences.json").exists():
            from services.dossier_edit_service import _write_table
            _write_table("sequences", counters)
        return counters


def next_reference(table):
    with data.LOCK:
        ensure_ready()
        counters = advance_sequences(data.load_store())
        if counters[table] >= MAX_NUMBER:
            raise ValueError(f"Séquence {PREFIXES[table]} épuisée : la limite de six chiffres est atteinte.")
        counters[table] += 1
        from services.dossier_edit_service import _write_table
        _write_table("sequences", counters)
        return f"{PREFIXES[table]}-{counters[table]:06d}"
