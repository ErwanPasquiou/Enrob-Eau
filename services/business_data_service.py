"""Données métier locales : aucune connexion à Databricks."""
import json
from datetime import date, datetime
from pathlib import Path
from threading import RLock

import pandas as pd
from services.data_model import SCHEMAS, DATE_FIELDS, BOOL_FIELDS

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "exemples"
LOCK = RLock()


def load_store():
    with LOCK:
        from services.reference_service import ensure_ready
        ensure_ready()
        store = {table: json.loads((DATA_DIR / f"{table}.json").read_text(encoding="utf-8-sig"))
                 for table in SCHEMAS}
        validate_store(store, normalized=True)
        return store


def validate_store(store, normalized=False):
    """Contrôle le schéma local et les relations, sans modifier les données."""
    for table, columns in SCHEMAS.items():
        rows = store[table]
        if not isinstance(rows, list):
            raise ValueError(f"{table} : une liste de lignes est attendue.")
        seen = set()
        saur_references = set()
        for index, row in enumerate(rows, 1):
            if isinstance(row, dict) and "WorkOrderReference" in row:
                raise ValueError("Ancien modèle local détecté. Exécutez la migration CODEX-001 avant de continuer (voir README).")
            if not isinstance(row, dict) or set(row) != set(columns):
                raise ValueError(f"{table}, ligne {index} : colonnes différentes du modèle.")
            key = row[columns[0]]
            if not isinstance(key, str) or not key.strip() or key in seen:
                raise ValueError(f"{table}, ligne {index} : référence vide ou dupliquée.")
            seen.add(key)
            if normalized:
                from services.reference_service import validate_reference
                validate_reference(table, key)
            if table == "interventions":
                reference = row["WorkOrderReferenceSaur"]
                if not isinstance(reference, str) or not reference.strip():
                    raise ValueError(f"Intervention {key} : la référence SI SAUR est obligatoire.")
                if reference.strip() in saur_references:
                    raise ValueError(f"Intervention {key} : référence SI SAUR dupliquée : {reference}.")
                saur_references.add(reference.strip())
            for field, value in row.items():
                if field == "DictAtuIndicator" and value not in {"DICT", "ATU", "NA"}:
                    raise ValueError(f"{table}, ligne {index} : DICT / ATU doit valoir DICT, ATU ou NA.")
                if field in DATE_FIELDS and value is not None:
                    try:
                        datetime.fromisoformat(value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"{table}, ligne {index}, {field} : date ISO attendue.") from exc
                if field in BOOL_FIELDS and value is not None and not isinstance(value, bool):
                    raise ValueError(f"{table}, ligne {index}, {field} : booléen attendu.")
    requests = {row["RequestReference"] for row in store["demandes"]}
    orders = {row["WorkOrderReferenceEnrobEau"] for row in store["interventions"]}
    for row in store["interventions"]:
        if row["RequestReference"] not in requests:
            raise ValueError(f"Intervention {row['WorkOrderReferenceEnrobEau']} : demande inexistante.")
    for row in store["prestations"]:
        if row["WorkOrderReferenceEnrobEau"] not in orders:
            raise ValueError(f"Prestation {row['ServiceReference']} : intervention inexistante.")


def related_records(store, reference):
    orders = [row for row in store["interventions"] if row["RequestReference"] == reference]
    ids = {row["WorkOrderReferenceEnrobEau"] for row in orders}
    return {"interventions": orders, "prestations": [row for row in store["prestations"] if row["WorkOrderReferenceEnrobEau"] in ids]}


def filter_store(store, query="", cities=(), statuses=(), period=()):
    """Filtre au niveau des dossiers puis propage les clés vers les enfants."""
    selected = []
    for row in store["demandes"]:
        linked = related_records(store, row["RequestReference"])
        records = [row, *linked["interventions"], *linked["prestations"]]
        text = " ".join(str(value) for record in records for value in record.values()).casefold()
        if any(word not in text for word in query.casefold().split()):
            continue
        if cities and row["ReportedCity"] not in cities:
            continue
        if statuses and row["RequestStatus"] not in statuses:
            continue
        if len(period) == 2 and (not row["RequestDate"] or not period[0] <= date.fromisoformat(row["RequestDate"][:10]) <= period[1]):
            continue
        selected.append(row)
    ids = {row["RequestReference"] for row in selected}
    orders = [row for row in store["interventions"] if row["RequestReference"] in ids]
    order_ids = {row["WorkOrderReferenceEnrobEau"] for row in orders}
    return dict(demandes=selected, interventions=orders,
                prestations=[row for row in store["prestations"] if row["WorkOrderReferenceEnrobEau"] in order_ids])


def table_frame(store, table, columns=None):
    return pd.DataFrame(store[table], columns=SCHEMAS[table]).loc[:, SCHEMAS[table] if columns is None else columns]


def export_csv(frame):
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    safe = frame.apply(lambda column: column.map(safe_cell))
    return safe.to_csv(index=False, sep=";", lineterminator="\n").encode("utf-8-sig")
