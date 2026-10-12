"""Conversion du classeur fourni, sans toucher aux données actives."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from services.business_data_service import validate_store
from services.data_model import SCHEMAS

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Le convertisseur PowerShell est destiné à Windows.")
class RequestImportTests(unittest.TestCase):
    def test_workbook_conversion_preserves_source_and_model(self):
        source = ROOT / "data/exemples/Demande.xlsx"
        digest = hashlib.sha256(source.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "demandes.json"
            command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(ROOT / "scripts/prepare_demandes.ps1"), "-Source", str(source),
                       "-OutputPath", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 4294)
            self.assertEqual(len({r["RequestReference"] for r in rows}), len(rows))
            self.assertTrue(all(set(r) == set(SCHEMAS["demandes"]) for r in rows))
            validate_store(dict(demandes=rows, interventions=[], prestations=[]), normalized=True)
            self.assertTrue(all(r["RequestStatus"] == "Migration" for r in rows))
            self.assertEqual(sum(r["RequestDate"] is None for r in rows), 894)
            self.assertEqual(sum('[Import Demande.xlsx - ReportedDiameter]' in (r["RequestComment"] or '') for r in rows), 534)
            self.assertEqual(sum('[Import Demande.xlsx - WaterShutdownIndicatorOther]' in (r["RequestComment"] or '') for r in rows), 78)
            saved = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True, timeout=120)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), saved)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), digest)
