from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services.reporting_demo_service import CITIES, PERIODS, snapshot, priority_rows

ROOT = Path(__file__).resolve().parents[1]


class ReportingTests(unittest.TestCase):
    def test_default_scenario_and_totals(self):
        data = snapshot()
        self.assertEqual(data["metrics"][:3], (13, 9, 3))
        self.assertAlmostEqual(data["metrics"][3], 7.444444444)
        self.assertEqual(round(data["metrics"][4]), 92)
        self.assertEqual(len(priority_rows(data["rows"])), 3)
        self.assertEqual(len(priority_rows(data["rows"], upcoming=True)), 2)
        for city in ("Toutes les communes", *CITIES):
            for period in PERIODS:
                with self.subTest(city=city, period=period):
                    selected = snapshot(city, period)
                    self.assertEqual(sum(selected["statuses"]), selected["metrics"][0])
                    self.assertEqual(sum(selected["cities"].values()), selected["metrics"][0])
                    self.assertEqual(sum(r["requests"] for r in selected["activity"]), selected["metrics"][0])
                    self.assertEqual(sum(r["completed"] for r in selected["activity"]), selected["metrics"][1])
                    self.assertTrue(all(selected["start"] <= r["created"] <= selected["end"] for r in selected["rows"]))
                    self.assertTrue(all(city == "Toutes les communes" or r["city"] == city for r in selected["rows"]))

    def test_page_filters_and_empty_selection_without_business_io(self):
        with patch("services.business_data_service.load_store", side_effect=AssertionError("Accès métier inattendu")):
            app = AppTest.from_file(str(ROOT / "pages/reporting_collectivite.py"))
            app.session_state["current_user"] = dict(actif=True, profil="agent", initials="EP")
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual({tab.label for tab in app.tabs},
                             {"Vue d’ensemble", "En retard (3)", "Prochaines échéances (2)",
                              "Performance", "Dossiers", "Photos", "Export"})
            app.selectbox(key="reporting_city").select("Saint-Chamond")
            app.selectbox(key="reporting_period").select("3 derniers mois").run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(snapshot("Saint-Chamond", "3 derniers mois")["rows"]), 0)
            self.assertIn("En retard (0)", [tab.label for tab in app.tabs])

    def test_denied_profiles_stop_before_demo_data(self):
        for user in ({}, dict(actif=True, profil="agent externe"), dict(actif=False, profil="agent")):
            with patch("services.reporting_demo_service.snapshot") as load:
                app = AppTest.from_file(str(ROOT / "pages/reporting_collectivite.py"))
                app.session_state["current_user"] = user
                app.run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.error)
                load.assert_not_called()
