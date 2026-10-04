from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class DossierPeriodTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        store = {
            table: json.loads((root / "data/exemples" / f"{table}.json").read_text(encoding="utf-8-sig"))
            for table in ("demandes", "interventions", "prestations")
        }
        # Exercise the page without writing local data or opening the photo database.
        self.enterContext(patch("services.business_data_service.load_store", return_value=store))
        self.enterContext(patch("components.photos.render_photos"))
        self.enterContext(patch("streamlit.elements.lib.policies._shown_default_value_warning", False))
        self.app = AppTest.from_file(str(root / "pages/gestion_des_dossiers.py"))
        self.app.session_state["current_user"] = {"actif": True, "profil": "agent", "initials": "TL"}
        self.period = (date(2020, 1, 1), date(2030, 12, 31))

    def assert_clean(self):
        self.assertEqual(len(self.app.exception), 0)
        self.assertFalse(any('widget with key "dossier_period"' in w.value for w in self.app.warning))

    def test_initially_empty_and_user_selection_persists(self):
        self.app.run(timeout=30)
        self.assert_clean()
        self.assertEqual(tuple(self.app.date_input(key="dossier_period").value), ())
        self.app.date_input(key="dossier_period").set_value(self.period).run(timeout=30)
        self.app.run(timeout=30)
        self.assert_clean()
        self.assertEqual(tuple(self.app.date_input(key="dossier_period").value), self.period)

    def test_save_resets_period_without_warning(self):
        self.app.run(timeout=30)
        selected = self.app.session_state["dossier_selected"]
        self.app.date_input(key="dossier_period").set_value(self.period).run(timeout=30)
        self.app.session_state["dossier_saved_ref"] = selected
        self.app.run(timeout=30)
        self.assert_clean()
        self.assertEqual(tuple(self.app.date_input(key="dossier_period").value), ())
        self.assertEqual(self.app.session_state["dossier_selected"], selected)

    def test_expand_restores_period_without_warning(self):
        self.app.run(timeout=30)
        self.app.date_input(key="dossier_period").set_value(self.period).run(timeout=30)
        selected = self.app.session_state["dossier_selected"]
        self.app.button(key="toggle_dossier_size").click().run(timeout=30)
        self.assert_clean()
        self.app.button(key="toggle_dossier_size").click().run(timeout=30)
        self.assert_clean()
        self.assertEqual(tuple(self.app.date_input(key="dossier_period").value), self.period)
        self.assertEqual(self.app.session_state["dossier_selected"], selected)
