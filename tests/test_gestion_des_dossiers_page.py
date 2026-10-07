from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest
from request_fixtures import isolate_local_data


class BusinessPagesTests(unittest.TestCase):
    def setUp(self):
        isolate_local_data(self)

    def test_service_dates_react_to_choices(self):
        from datetime import date
        app = AppTest.from_string('''
from components.dossier_forms import render_record_form
render_record_form("prestations", "REQ-test", parent={"WorkOrderReferenceEnrobEau": "WO-test", "WorkOrderReferenceSaur": "SAUR-test"})
''').run(timeout=30)
        next(w for w in app.date_input if w.key.endswith("_BackfillDate")).set_value(date(2026, 9, 20)).run()
        next(w for w in app.selectbox if w.key.endswith("_HasConcrete2Cm")).set_value(True).run()
        self.assertEqual(len(app.exception), 0)
        automatic = next(w for w in app.text_input if w.key.endswith("_Concrete2CmDate_auto"))
        self.assertEqual(automatic.value, "2026-09-20")
        self.assertTrue(automatic.disabled)
        next(w for w in app.selectbox if w.key.endswith("_HasConcrete2Cm")).set_value(False).run()
        self.assertTrue(any(w.key.endswith("_Concrete2CmDate") for w in app.date_input))

    def test_forms_lists_only_connected_email_and_opens_new_form(self):
        from services.business_data_service import load_store
        store = load_store()
        email = store["demandes"][0]["RequesterReference"]
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages/forms.py"))
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "email": email.upper()}
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        expected = {r["RequestReference"] for r in store["demandes"] if r["RequesterReference"].casefold() == email.casefold()}
        self.assertEqual({b.key.removeprefix("forms_view_") for b in app.button if b.key and b.key.startswith("forms_view_")}, expected)
        app.button(key=f"forms_view_{store['demandes'][0]['RequestReference']}").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(m.value == "### Photos" for m in app.markdown))
        app.button(key="forms_modify").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(w.disabled and w.value.casefold() == email.casefold() for w in app.text_input))
        next(b for b in app.button if b.label == "Nouveau").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(w.value == email.upper() and w.disabled for w in app.text_input))

    def create_app(self, name):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages" / name))
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "initials": "TL"}
        return app.run(timeout=30)

    def test_dossier_fields_and_selection(self):
        app = self.create_app("gestion_des_dossiers.py")
        self.assertEqual(len(app.exception), 0)
        app.button(key="gd_select_DEM-000011").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["dossier_selected"], "DEM-000011")

    def test_expand_and_restore_dossier(self):
        app = self.create_app("gestion_des_dossiers.py")
        selected = app.session_state["dossier_selected"]
        app.button(key="toggle_dossier_size").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state["dossier_expanded"])
        self.assertFalse(any(widget.label == "Rechercher" for widget in app.text_input))
        app.button(key="toggle_dossier_size").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.session_state["dossier_expanded"])
        self.assertEqual(app.session_state["dossier_selected"], selected)

    def test_export_and_no_columns(self):
        app = self.create_app("export.py")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 3)
        app.multiselect(key="export_columns_demandes").set_value([]).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 2)


if __name__ == "__main__":
    unittest.main()
