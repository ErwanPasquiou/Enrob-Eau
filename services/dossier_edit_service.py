"""Écriture atomique des fichiers métier locaux avec contrôle des modifications concurrentes."""
from copy import deepcopy
from datetime import datetime
import json
import os
import re
import tempfile

from services import business_data_service as data
from services.data_model import SCHEMAS, DATE_FIELDS, BOOL_FIELDS
from services.reference_service import next_reference, validate_reference, advance_sequences

LOCK = data.LOCK
STATUSES = {
    "RequestStatus": ["À traiter", "En cours", "En attente", "Refusée", "Clôturée"],
    "WorkOrderStatus": ["À planifier", "En cours", "En attente", "Clôturée"],
    "ServiceStatus": ["À planifier", "En cours", "En attente", "Terminée"],
}
STATUS_FIELD = {"demandes": "RequestStatus", "interventions": "WorkOrderStatus", "prestations": "ServiceStatus"}
BLOCKED_REQUESTS = {"En attente", "Refusée", "Clôturée"}


def new_record(table, parent=None):
    now = datetime.now().isoformat(timespec="seconds")
    row = {field: None for field in SCHEMAS[table]}
    row[SCHEMAS[table][0]] = next_reference(table)
    row.update(CreatedAt=now, UpdatedAt=now)
    for field in BOOL_FIELDS & row.keys():
        row[field] = False
    row[STATUS_FIELD[table]] = "À traiter" if table == "demandes" else "En cours"
    if table == "demandes":
        row["RequestDate"] = now[:10]
        row["DictAtuIndicator"] = "NA"
    elif table == "interventions":
        row["RequestReference"] = parent["RequestReference"]
    else:
        row["WorkOrderReferenceEnrobEau"] = parent["WorkOrderReferenceEnrobEau"]
        row["HasConcrete2Cm"] = None
        row["HasTemporaryRepair"] = None
    return row


def validate_record(table, row):
    if set(row) != set(SCHEMAS[table]):
        raise ValueError("Les champs ne correspondent pas au modèle.")
    required = {"demandes": ["RequestReason", "ReportedCity", "RequestDate"],
                "interventions": ["WorkOrderReferenceEnrobEau", "WorkOrderReferenceSaur", "RequestReference"],
                "prestations": ["WorkOrderReferenceEnrobEau", "WorkReason", "WorkCity"]}[table]
    for field in required:
        if row[field] is None or not str(row[field]).strip():
            from services.data_model import LABELS
            raise ValueError(f"Le champ « {LABELS[field]} » est obligatoire.")
    key = row[SCHEMAS[table][0]]
    if not isinstance(key, str) or not key.strip():
        raise ValueError("L'identifiant technique est obligatoire.")
    validate_reference(table, key)
    if row[STATUS_FIELD[table]] not in STATUSES[STATUS_FIELD[table]]:
        raise ValueError("Statut invalide.")
    for field, value in row.items():
        if field in DATE_FIELDS and value is not None:
            datetime.fromisoformat(value)
        if field in BOOL_FIELDS and value is not None and type(value) is not bool:
            raise ValueError(f"{field} : valeur booléenne attendue.")
    if table == "demandes":
        if row["DictAtuIndicator"] not in {"DICT", "ATU", "NA"}:
            raise ValueError("DICT / ATU : choisissez DICT, ATU ou NA.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(row["RequesterReference"] or "")):
            raise ValueError("Renseignez une adresse e-mail valide pour le demandeur.")
        for field in ("ReportedDiameter", "EstimatedWorkDays"):
            if row[field] is not None and float(row[field]) < 0:
                raise ValueError("Le diamètre et la durée doivent être positifs.")
    if table == "interventions":
        if (row["WorkOrderStatus"] == "Clôturée") != bool(row["ClosedAt"]):
            raise ValueError("Le statut Clôturée et la date de clôture doivent être renseignés ensemble.")
        # Ces deux dates concernent la DICT / l'ATU, pas le cycle de l'intervention.
        chain = [row[f] for f in ("IssuedAt", "ReceivedAt") if row[f]]
    elif table == "prestations":
        for flag, field in (("HasConcrete2Cm", "Concrete2CmDate"), ("HasTemporaryRepair", "TemporaryRepairDate")):
            if row[flag] is True and (not row["BackfillDate"] or row[field] != row["BackfillDate"]):
                raise ValueError("La date de réalisation doit reprendre la date de remblaiement.")
            if row[flag] is False and not row[field]:
                raise ValueError("Saisissez manuellement la date du béton ou de la réfection provisoire lorsque Non est sélectionné.")
        if (row["ServiceStatus"] == "Terminée") != bool(row["FinalRepairDate"]):
            raise ValueError("Le statut Terminée et la date de réfection définitive doivent être renseignés ensemble.")
        chain = [row[f] for f in ("ExcavationDate", "BackfillDate", "Concrete2CmDate", "TemporaryRepairDate", "FinalRepairDate") if row[f]]
    else:
        chain = []
    if any(datetime.fromisoformat(a) > datetime.fromisoformat(b) for a, b in zip(chain, chain[1:])):
        raise ValueError("Les dates doivent respecter l'ordre des travaux.")


def save_record(table, row, original=None, photos=(), actor="", owner_email=None):
    """Écrit une table ; refuse d'écraser une fiche modifiée depuis son ouverture."""
    with LOCK:
        store = data.load_store()
        before = deepcopy(store)
        row = deepcopy(row)
        pk = SCHEMAS[table][0]
        if table == "interventions":
            reference = row["WorkOrderReferenceSaur"]
            if not isinstance(reference, str) or not reference.strip():
                raise ValueError("La référence de l'intervention SI SAUR est obligatoire.")
            row["WorkOrderReferenceSaur"] = reference.strip()
        current = next((r for r in store[table] if r[pk] == row[pk]), None)
        if owner_email is not None:
            if table != "demandes" or not owner_email.strip():
                raise ValueError("Utilisateur non identifié.")
            if current and str(current["RequesterReference"] or "").strip().casefold() != owner_email.strip().casefold():
                raise ValueError("Vous ne pouvez modifier que vos propres demandes.")
            row["RequesterReference"] = current["RequesterReference"] if current else owner_email
        if (original is None and current is not None) or (original is not None and current != original):
            raise ValueError("Cette fiche a changé. Fermez puis rouvrez le formulaire avant de réessayer.")
        if original:
            for field in (pk, "CreatedAt", "RequestReference" if table == "interventions" else "WorkOrderReferenceEnrobEau" if table == "prestations" else pk):
                if row[field] != original[field]:
                    raise ValueError("Les références et les liens existants ne sont pas modifiables.")
        if table == "interventions" and any(
            r[pk] != row[pk] and r["WorkOrderReferenceSaur"].strip() == row["WorkOrderReferenceSaur"]
            for r in store["interventions"]
        ):
            raise ValueError("Cette référence SI SAUR existe déjà pour une autre intervention. Renseignez une référence unique.")
        if table != "demandes":
            if table == "interventions":
                request_id = row["RequestReference"]
            else:
                order = next((r for r in store["interventions"] if r["WorkOrderReferenceEnrobEau"] == row["WorkOrderReferenceEnrobEau"]), None)
                if order is None:
                    raise ValueError("Intervention introuvable.")
                if original is None and order["WorkOrderStatus"] in {"Clôturée", "En attente"}:
                    raise ValueError("Réactivez l'intervention avant de créer une prestation.")
                request_id = order["RequestReference"]
            request = next((r for r in store["demandes"] if r["RequestReference"] == request_id), None)
            if request is None:
                raise ValueError("Demande introuvable.")
            if original is None and request["RequestStatus"] in BLOCKED_REQUESTS:
                raise ValueError("Reprenez le traitement de la demande avant de créer des travaux.")
        row["UpdatedAt"] = datetime.now().isoformat(timespec="microseconds")
        if table == "interventions":
            for field in ("IssuedAt", "ReceivedAt", "ClosedAt", "CityInformedAt", "CustomerInformedAt"):
                if row[field]:
                    row[field] = datetime.fromisoformat(row[field]).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            if row["ClosedAt"]:
                row["WorkOrderStatus"] = "Clôturée"
        if table == "prestations":
            for flag, field in (("HasConcrete2Cm", "Concrete2CmDate"), ("HasTemporaryRepair", "TemporaryRepairDate")):
                if row[flag] is True:
                    row[field] = row["BackfillDate"]
        validate_record(table, row)
        records = store[table]
        if current is None:
            records.append(row)
        else:
            records[records.index(current)] = row
        if table != "demandes":
            propagate_closures(store, request_id, row["UpdatedAt"])

        def save_photos():
            from services.photo_service import add_photos
            add_photos(table, row[pk], photos, actor, owner_email)

        # Les compteurs ne sont pas annulés si l'écriture métier échoue.
        advance_sequences(store)
        _persist_changes(before, store, save_photos if photos else None)
    return row


def propagate_closures(store, request_ref, stamp):
    """Clôture ascendante, limitée au dossier concerné et aux ensembles non vides."""
    orders = [r for r in store["interventions"] if r["RequestReference"] == request_ref]
    for order in orders:
        services = [r for r in store["prestations"] if r["WorkOrderReferenceEnrobEau"] == order["WorkOrderReferenceEnrobEau"]]
        if services and all(r["ServiceStatus"] == "Terminée" and r["FinalRepairDate"] for r in services):
            if order["WorkOrderStatus"] != "Clôturée" or not order["ClosedAt"]:
                last_day = max(datetime.fromisoformat(r["FinalRepairDate"]).date() for r in services)
                order.update(WorkOrderStatus="Clôturée", ClosedAt=last_day.isoformat() + "T00:00:00", UpdatedAt=stamp)
    request = next(r for r in store["demandes"] if r["RequestReference"] == request_ref)
    if orders and all(r["WorkOrderStatus"] == "Clôturée" for r in orders):
        if request["RequestStatus"] not in {"Clôturée", "Refusée"}:
            request.update(RequestStatus="Clôturée", UpdatedAt=stamp)


def _persist_changes(before, after, after_write=None):
    """Compense les écritures locales déjà effectuées si une étape échoue."""
    written = []
    try:
        for table in SCHEMAS:
            if before[table] != after[table]:
                _write_table(table, after[table])
                written.append(table)
        if after_write:
            after_write()
    except (ValueError, OSError):
        for table in reversed(written):
            _write_table(table, before[table])
        raise


def change_request_status(original, status, reason=""):
    if status in {"En attente", "Refusée"} and not reason.strip():
        raise ValueError("Précisez le motif de cette décision.")
    row = deepcopy(original)
    row["RequestStatus"] = status
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    entry = f"[{stamp}] {status}" + (f" : {reason.strip()}" if reason.strip() else "")
    row["RequestComment"] = ((row["RequestComment"] or "") + "\n" + entry).strip()
    return save_record("demandes", row, original)


def _write_table(table, records):
    path = data.DATA_DIR / f"{table}.json"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as temp:
            temp_path = temp.name
            json.dump(records, temp, ensure_ascii=False, indent=2)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def delete_record(table, original):
    if table not in {"interventions", "prestations"}:
        raise ValueError("Seules les interventions et prestations peuvent être supprimées.")
    with LOCK:
        store = data.load_store()
        before = deepcopy(store)
        pk = SCHEMAS[table][0]
        current = next((r for r in store[table] if r[pk] == original[pk]), None)
        if current != original:
            raise ValueError("Cette fiche a changé ou a été supprimée. Actualisez le dossier.")
        if table == "interventions" and any(r["WorkOrderReferenceEnrobEau"] == original[pk] for r in store["prestations"]):
            raise ValueError("Impossible de supprimer une intervention qui possède des prestations.")
        if table == "prestations":
            from services.photo_service import list_photos
            if list_photos(table, original[pk]):
                raise ValueError("Supprimez les photos de la prestation avant de supprimer cette prestation.")
        if table == "interventions":
            request_ref = current["RequestReference"]
        else:
            request_ref = next(r["RequestReference"] for r in store["interventions"] if r["WorkOrderReferenceEnrobEau"] == current["WorkOrderReferenceEnrobEau"])
        store[table] = [r for r in store[table] if r[pk] != original[pk]]
        advance_sequences(before)
        propagate_closures(store, request_ref, datetime.now().isoformat(timespec="microseconds"))
        _persist_changes(before, store)
