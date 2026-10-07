"""Référentiels et adaptation non destructive des demandes locales (CODEX-003)."""
from copy import deepcopy


REQUEST_CHOICES = {
    "ReportedRoadType": ["Pleine terre", "Chaussée", "Trottoir", "Autre"],
    "DictAtuIndicator": ["ATU immédiate", "ATU 72h", "ATU sous 9 jours", "DICT", "Sans terrassement"],
    "ReportedSurfaceType": ["Enrobé", "Asphalte <= 3m2", "Asphalte > 3m2", "Béton désactivé",
                            "Béton (résine) perméable", "Pleine terre", "Pavé"],
    "RequestReason": ["Création branchement neuf", "Réparation de fuite branchement",
                      "Renouvellement de branchement", "Suppression de branchement",
                      "Modification de branchement", "Intervention bouche à clés", "Renouvellement de regard",
                      "Réparation fuite réseau distribution", "Sondage", "Pose d'une vanne réseau",
                      "Réparation une vanne réseau", "Renouvellement vanne réseau", "Création PI",
                      "Renouvellement PI", "Pose Borne Moneca"],
    "WaterShutdownIndicator": ["Avec arrêt d'eau 1 jour", "Avec arrêt d'eau 1/2 journée", "Sans arrêt d'eau", "Autre"],
    "ReportedMaterial": ["Fonte", "PVC", "PEHD", "PEBD", "Cuivre", "Acier - Fer - Galva", "Plomb", "Non détectable", "Autre"],
    "BusinessDomain": ["En domaine public : en agglomération", "En domaine public : Route métropolitaine",
                       "En domaine privé nécessitant RDV"],
    "RoadImpact": ["Route barrée et déviation", "Alternat par feu", "Réduction sur chaussée",
                   "Pose de panneaux interdit de stationner", "Travaux sur trottoir", "Aucun impact", "Autre"],
}
MULTIPLE_FIELDS = {"ReportedRoadType", "ReportedSurfaceType", "RoadImpact"}
OPTIONAL_NEW_FIELDS = {"MeterReference", "ReportedRoadTypeOther"}


def adapt_request(source):
    """Complète les champs absents et encapsule le texte sans interpréter son sens.

    Les anciens booléens et les valeurs hors référentiel restent lisibles. Leur
    remplacement est une décision de l'utilisateur à l'enregistrement du formulaire.
    """
    row = deepcopy(source)
    for field in OPTIONAL_NEW_FIELDS:
        row.setdefault(field, None)
    for field in MULTIPLE_FIELDS:
        if isinstance(row.get(field), str):
            row[field] = [row[field]] if row[field] else []
    return row


def validate_request_types(row):
    """Types de stockage, avec lecture des représentations historiques."""
    from services.data_model import LABELS
    for field in OPTIONAL_NEW_FIELDS:
        if row.get(field) is not None and not isinstance(row[field], str):
            raise ValueError(f"{field} : texte ou null attendu.")
    for field in REQUEST_CHOICES:
        value = row[field]
        if value is None:
            continue
        if field in {"RoadImpact", "WaterShutdownIndicator"} and type(value) is bool:
            continue  # Ancienne représentation, jamais proposée à la création.
        if field in MULTIPLE_FIELDS:
            if isinstance(value, str) or (isinstance(value, list) and all(isinstance(v, str) for v in value)):
                continue
        elif isinstance(value, str):
            continue
        raise ValueError(f"{LABELS[field]} : type de donnée invalide.")


def validate_request_choices(row):
    from services.data_model import LABELS
    validate_request_types(row)
    for field, options in REQUEST_CHOICES.items():
        value = row[field]
        valid = (isinstance(value, list) and bool(value) and all(v in options for v in value)
                 if field in MULTIPLE_FIELDS else isinstance(value, str) and value in options)
        if not valid:
            raise ValueError(f"Le champ « {LABELS[field]} » est obligatoire : choisissez uniquement les valeurs proposées.")
    if "Autre" in row["ReportedRoadType"] and not (row.get("ReportedRoadTypeOther") or "").strip():
        raise ValueError("Précisez le type de voirie lorsque « Autre » est sélectionné.")
    if row["RequestReason"] == "Renouvellement de branchement" and not (row.get("MeterReference") or "").strip():
        raise ValueError("Le champ « Matricule Compteur » est obligatoire pour un renouvellement de branchement.")
    for field in ("ReportedDiameter", "EstimatedWorkDays"):
        if row[field] is None or (isinstance(row[field], str) and not row[field].strip()):
            raise ValueError(f"Le champ « {LABELS[field]} » est obligatoire.")


def display_choices(value):
    """Libellé lisible également utilisable pour préremplir une prestation texte."""
    return ", ".join(value) if isinstance(value, list) else value
