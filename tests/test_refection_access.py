from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services.access_service import PAGES, PROFILS, can_access, default_page, page_href
from services.business_data_service import load_store
from services.refection_service import prestation_rows, filter_prestations
from request_fixtures import isolate_local_data

ROOT = Path(__file__).resolve().parents[1]


class RefectionAccessTests(unittest.TestCase):
    def setUp(self):
        isolate_local_data(self)

    def test_permissions_and_default_routes(self):
        expected = {
            "agent": {"accueil", "forms", "refection", "dossiers", "export"},
            "ordonnanceur": {"accueil", "forms", "refection", "dossiers", "export"},
            "agent externe": {"refection"},
            "administrateur": {p[0] for p in PAGES},
            "collectivité": set(),
        }
        for profile, pages in expected.items():
            self.assertEqual({p[0] for p in PAGES if can_access(profile, p[0])}, pages)
        self.assertNotIn("collectivité", PROFILS)
        self.assertEqual(default_page("agent"), "forms")
        self.assertEqual(default_page("agent externe"), "refection")
        self.assertEqual(page_href("agent", "forms", "forms"), "./")
        self.assertEqual(page_href("agent", "accueil", "accueil"), "./accueil")

    def test_external_direct_access_is_denied_before_loading_data(self):
        for script in ["accueil.py", "forms.py", "gestion_des_dossiers.py", "export.py", "administration.py"]:
            with self.subTest(script=script), patch("services.business_data_service.load_store") as load:
                app = AppTest.from_file(str(ROOT / "pages" / script))
                app.session_state["current_user"] = {"actif": True, "profil": "agent externe"}
                app.run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.error)
                load.assert_not_called()

    def test_app_registers_role_default_page(self):
        for profile, title in [("agent", "Demandes"), ("agent externe", "Réfection définitive")]:
            user = dict(id=1, nom="Test", prenom="Test", email="test@example.test", actif=True, profil=profile)
            with self.subTest(profile=profile), patch("services.auth_service.get_connected_email", return_value=user["email"]), patch("services.auth_service.get_current_user", return_value=user):
                # AppTest 1.38 n'exécute pas les pages st.navigation ; vérifier
                # les pages réelles enregistrées par app.py auprès du routeur.
                with patch("streamlit.navigation") as navigation:
                    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
                self.assertFalse(app.exception)
                pages = navigation.call_args.args[0]
                self.assertEqual([p.title for p in pages if p.url_path == ""], [title])
                if profile == "agent externe":
                    self.assertEqual(len(pages), 1)

    def test_filters_preserve_parent_links(self):
        store = load_store()
        rows = prestation_rows(store)
        orders = {r["WorkOrderReferenceEnrobEau"]: r for r in store["interventions"]}
        self.assertEqual(len(rows), len(store["prestations"]))
        for row in rows:
            self.assertEqual(row["RequestReference"], orders[row["WorkOrderReferenceEnrobEau"]]["RequestReference"])
        selected = rows[0]
        filtered = filter_prestations(rows, selected["ServiceReference"], [selected["WorkCity"]], [selected["ServiceStatus"]])
        self.assertEqual(filtered, [selected])
        self.assertTrue(all(not r["FinalRepairDate"] for r in filter_prestations(rows, repair="À réaliser")))
        self.assertTrue(all(r["FinalRepairDate"] for r in filter_prestations(rows, repair="Réalisées")))

    def test_dossier_create_service_button_requires_available_intervention(self):
        store = load_store()
        for available in [False, True]:
            request = next(r for r in store["demandes"] if r["RequestStatus"] not in {"Refusée", "Clôturée", "En attente"})
            order = dict(store["interventions"][0], RequestReference=request["RequestReference"], WorkOrderStatus="En cours")
            data = {"demandes": [request], "interventions": [order] if available else [], "prestations": []}
            with patch("services.business_data_service.load_store", return_value=data):
                app = AppTest.from_file(str(ROOT / "pages/gestion_des_dossiers.py"))
                app.session_state["current_user"] = {"actif": True, "profil": "ordonnanceur"}
                app.run(timeout=30)
                self.assertFalse(app.exception)
                button = next(b for b in app.button if b.label == "Créer une prestation")
                self.assertEqual(button.disabled, not available)
                if available:
                    button.click().run(timeout=30)
                    self.assertFalse(app.exception)
                    self.assertEqual(next(s for s in app.selectbox if s.label == "Intervention concernée *").value, order["WorkOrderReferenceEnrobEau"])
