"""Données valides de formulaire, réservées aux tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch


VALID_CHOICES = {
    "RequestReason": "Sondage", "BusinessDomain": "En domaine public : en agglomération",
    "ReportedMaterial": "Fonte", "ReportedRoadType": ["Chaussée"], "ReportedSurfaceType": ["Enrobé"],
    "RoadImpact": ["Aucun impact"], "DictAtuIndicator": "DICT", "WaterShutdownIndicator": "Sans arrêt d'eau",
}


def valid_choices():
    return deepcopy(VALID_CHOICES)


def isolate_local_data(case):
    """Les tests de widgets ne doivent pas consommer les compteurs du projet."""
    from services import business_data_service as data
    store = data.load_store()
    folder = tempfile.TemporaryDirectory()
    case.addCleanup(folder.cleanup)
    root = Path(folder.name)
    for table, rows in store.items():
        (root / f"{table}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    case.enterContext(patch.object(data, "DATA_DIR", root))
    return root
