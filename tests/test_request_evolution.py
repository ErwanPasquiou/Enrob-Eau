from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services import business_data_service as data
from services import dossier_edit_service as edits
from services.data_model import SCHEMAS
from services.request_model import REQUEST_CHOICES, MULTIPLE_FIELDS, adapt_request
from request_fixtures import valid_choices


class RequestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for table in SCHEMAS:
            (self.root / f"{table}.json").write_text("[]", encoding="utf-8")
        self.enterContext(patch.object(data, "DATA_DIR", self.root))

    def request(self):
        return dict(edits.new_record("demandes"), **valid_choices(), ReportedCity="Test",
                    ReportedAdress="1 rue de Test", RequesterReference="agent@example.test")

    def content(self):
        return {table: (self.root / f"{table}.json").read_bytes() for table in SCHEMAS}


class RequestEvolutionTests(RequestCase):
    def test_defaults_have_no_invented_business_values(self):
        row = edits.new_record("demandes")
        for field in REQUEST_CHOICES:
            self.assertEqual(row[field], [] if field in MULTIPLE_FIELDS else None)
        self.assertIsNone(row["MeterReference"])
        self.assertIsNone(row["ReportedRoadTypeOther"])

    def test_each_authorized_value_and_required_fields(self):
        row = self.request()
        for field, options in REQUEST_CHOICES.items():
            for option in options:
                with self.subTest(field=field, option=option):
                    candidate = dict(row, MeterReference="000123", ReportedRoadTypeOther="Précision")
                    candidate[field] = [option] if field in MULTIPLE_FIELDS else option
                    edits.validate_record("demandes", candidate)
            for bad in (None, "", [], "Inconnue", ["Inconnue"], True, 1, {}):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    edits.validate_record("demandes", dict(row, **{field: bad}))

    def test_multi_choices_save_reload_edit_and_csv(self):
        row = self.request()
        row.update(ReportedRoadType=["Chaussée", "Trottoir"], ReportedSurfaceType=["Enrobé", "Pavé"],
                   RoadImpact=["Alternat par feu", "Travaux sur trottoir"], MeterReference="000123")
        saved = edits.save_record("demandes", row)
        self.assertEqual(data.load_store()["demandes"][0], saved)
        raw = json.loads((self.root / "demandes.json").read_text(encoding="utf-8"))[0]
        for field in MULTIPLE_FIELDS:
            self.assertEqual(raw[field], row[field])
        updated = edits.save_record("demandes", dict(saved, ReportedRoadType=["Pleine terre", "Trottoir"]), saved)
        frame = data.table_frame(data.load_store(), "demandes")
        exported = next(csv.DictReader(io.StringIO(data.export_csv(frame).decode("utf-8-sig")), delimiter=";"))
        for field in MULTIPLE_FIELDS:
            self.assertEqual(json.loads(exported[field]), updated[field])
        self.assertEqual(exported["MeterReference"], "000123")
        self.assertEqual(data.filter_store(data.load_store(), query="Pleine terre")["demandes"], [updated])

    def test_other_precision_is_conditional(self):
        row = self.request()
        row["ReportedRoadType"] = ["Chaussée", "Autre"]
        for value in (None, "", "   "):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Précisez"):
                edits.save_record("demandes", dict(row, ReportedRoadTypeOther=value))
        self.assertEqual(data.load_store()["demandes"], [])
        saved = edits.save_record("demandes", dict(row, ReportedRoadTypeOther="Accès chantier"))
        updated = edits.save_record("demandes", dict(saved, ReportedRoadType=["Chaussée"], ReportedRoadTypeOther=None), saved)
        self.assertIsNone(updated["ReportedRoadTypeOther"])

    def test_meter_conditional_nullable_text_and_changes_of_reason(self):
        row = self.request()
        saved = edits.save_record("demandes", dict(row, MeterReference="   "))
        self.assertIsNone(saved["MeterReference"])
        before = self.content()
        for value in (None, "", " "):
            with self.assertRaisesRegex(ValueError, "Matricule Compteur"):
                edits.save_record("demandes", dict(saved, RequestReason="Renouvellement de branchement", MeterReference=value), saved)
        self.assertEqual(self.content(), before)
        renewed = edits.save_record("demandes", dict(saved, RequestReason="Renouvellement de branchement", MeterReference="000123"), saved)
        self.assertEqual(renewed["MeterReference"], "000123")
        optional = edits.save_record("demandes", dict(renewed, RequestReason="Sondage", MeterReference=None), renewed)
        self.assertIsNone(optional["MeterReference"])
        with self.assertRaises(ValueError):
            edits.save_record("demandes", dict(optional, MeterReference=123), optional)

    def test_legacy_read_is_lossless_and_status_change_still_works(self):
        old = self.request()
        old.pop("MeterReference")
        old.pop("ReportedRoadTypeOther")
        old.update(ReportedRoadType="Communale", ReportedSurfaceType="Enrobé", RoadImpact=True,
                   WaterShutdownIndicator=False, DictAtuIndicator="ATU", RequestReason="Ancien motif", ImpactTransport=True)
        (self.root / "demandes.json").write_text(json.dumps([old]), encoding="utf-8")
        before = self.content()
        loaded = data.load_store()["demandes"][0]
        self.assertIsNone(loaded["MeterReference"])
        self.assertEqual(loaded["ReportedRoadType"], ["Communale"])
        self.assertEqual(loaded["ReportedSurfaceType"], ["Enrobé"])
        self.assertIs(loaded["RoadImpact"], True)
        self.assertIs(loaded["WaterShutdownIndicator"], False)
        self.assertEqual(loaded["DictAtuIndicator"], "ATU")
        self.assertEqual(self.content(), before)
        with self.assertRaises(ValueError):
            edits.save_record("demandes", loaded, loaded)
        waiting = edits.change_request_status(loaded, "En attente", "Attente commune")
        for field in loaded:
            if field not in {"RequestStatus", "RequestComment", "UpdatedAt"}:
                self.assertEqual(waiting[field], loaded[field])
        with self.assertRaisesRegex(ValueError, "autres champs"):
            edits.save_record("demandes", dict(waiting, CustomerName="Contournement"), waiting, _status_only=True)

    def test_existing_links_photos_transport_and_concurrency_survive_edit(self):
        from services import photo_service as photos
        from test_photo_service import image_bytes
        old = self.request()
        old.pop("MeterReference")
        old.pop("ReportedRoadTypeOther")
        old["ImpactTransport"] = True
        (self.root / "demandes.json").write_text(json.dumps([old]), encoding="utf-8")
        loaded = data.load_store()["demandes"][0]
        order = edits.save_record("interventions", dict(edits.new_record("interventions", loaded), WorkOrderReferenceSaur="SAUR-test"))
        photos.add_photos("demandes", loaded["RequestReference"], [photos.prepare_photo("photo.png", image_bytes(), photo_name="Vue")], "agent@example.test")
        photo_bytes = (self.root / "photos.sqlite3").read_bytes()
        before = self.content()
        saved = edits.save_record("demandes", dict(loaded, **valid_choices(), MeterReference="0001"), loaded, owner_email="agent@example.test")
        self.assertEqual(saved["RequestReference"], old["RequestReference"])
        self.assertEqual(saved["CreatedAt"], old["CreatedAt"])
        self.assertIs(saved["ImpactTransport"], True)
        self.assertEqual(data.related_records(data.load_store(), saved["RequestReference"])["interventions"], [order])
        self.assertEqual(self.content()["interventions"], before["interventions"])
        self.assertEqual(self.content()["prestations"], before["prestations"])
        self.assertEqual((self.root / "photos.sqlite3").read_bytes(), photo_bytes)
        with self.assertRaisesRegex(ValueError, "a changé"):
            edits.save_record("demandes", loaded, loaded)
        with self.assertRaisesRegex(ValueError, "propres demandes"):
            edits.save_record("demandes", saved, saved, owner_email="autre@example.test")

    def test_loader_rejects_corrupt_types_and_unknown_columns(self):
        row = self.request()
        for change in ({"MeterReference": 123}, {"RoadImpact": [True]}, {"ReportedSurfaceType": {}}, {"Invented": None}):
            (self.root / "demandes.json").write_text(json.dumps([dict(row, **change)]), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(ValueError):
                data.load_store()

    def test_legacy_renewal_without_meter_loads_but_requires_it_on_save(self):
        old = self.request()
        old.pop("MeterReference")
        old.pop("ReportedRoadTypeOther")
        old["RequestReason"] = "Renouvellement de branchement"
        (self.root / "demandes.json").write_text(json.dumps([old]), encoding="utf-8")
        loaded = data.load_store()["demandes"][0]
        self.assertIsNone(loaded["MeterReference"])
        with self.assertRaisesRegex(ValueError, "Matricule Compteur"):
            edits.save_record("demandes", loaded, loaded)
        updated = edits.save_record("demandes", dict(loaded, MeterReference="0005"), loaded)
        self.assertEqual(updated["RequestReference"], old["RequestReference"])

    def test_codex001_migration_keeps_old_request_values_and_missing_fields(self):
        from services.local_model_migration import adapt_store
        old = self.request()
        old.pop("MeterReference")
        old.pop("ReportedRoadTypeOther")
        old.update(ReportedRoadType="Communale", RoadImpact=True, WaterShutdownIndicator=False)
        store = {"demandes": [old], "interventions": [], "prestations": []}
        self.assertEqual(adapt_store(store), store)

    def test_status_change_preserves_existing_optional_text_verbatim(self):
        row = dict(self.request(), MeterReference=" 0005 ", ReportedRoadTypeOther=" Ancienne précision ")
        (self.root / "demandes.json").write_text(json.dumps([row]), encoding="utf-8")
        loaded = data.load_store()["demandes"][0]
        changed = edits.change_request_status(loaded, "En attente", "En attente d'accord")
        self.assertEqual(changed["MeterReference"], row["MeterReference"])
        self.assertEqual(changed["ReportedRoadTypeOther"], row["ReportedRoadTypeOther"])


class RequestFormTests(RequestCase):
    def app(self, original=None, mobile=True):
        app = AppTest.from_string(f'''
import streamlit as st
from components.dossier_forms import render_record_form
if not st.session_state.get("forms_saved") and not st.session_state.get("dossier_saved_ref"):
    original = st.session_state.get("original")
    render_record_form("demandes", original["RequestReference"] if original else None,
                       original=original, mobile={mobile!r})
''')
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "email": "agent@example.test"}
        if original:
            app.session_state["original"] = original
        return app.run(timeout=30)

    def widget(self, app, kind, field):
        return next(w for w in getattr(app, kind) if w.key.endswith("_" + field))

    def fill(self, app):
        next(w for w in app.radio if w.key.endswith("_mode")).set_value("Autre / saisie libre").run()
        self.widget(app, "text_input", "address").set_value("1 rue Test")
        self.widget(app, "text_input", "city").set_value("Test")
        for field, value in valid_choices().items():
            self.widget(app, "multiselect" if field in MULTIPLE_FIELDS else "selectbox", field).set_value(value)
        app.run()

    def test_five_sections_lists_hidden_transport_and_identity(self):
        app = self.app()
        self.assertFalse(app.exception)
        expected = ["Localisation des travaux", "Informations sur la demande", "Caractéristiques des travaux",
                    "Contraintes et préparation du chantier", "Commentaire complémentaire"]
        self.assertEqual([m.value for m in app.markdown if m.value in [f"**{s}**" for s in expected]], [f"**{s}**" for s in expected])
        self.assertEqual(len(app.tabs), 0)
        for field, options in REQUEST_CHOICES.items():
            widget = self.widget(app, "multiselect" if field in MULTIPLE_FIELDS else "selectbox", field)
            self.assertEqual(widget.options, options)
            self.assertTrue(widget.label.endswith(" *"))
        self.assertFalse(any(w.key.endswith("_ImpactTransport") for kind in ("selectbox", "text_input", "multiselect") for w in getattr(app, kind)))
        email = self.widget(app, "text_input", "RequesterReference")
        self.assertTrue(email.disabled)
        self.assertEqual(email.value, "agent@example.test")

    def test_creation_multiple_values_then_edit_preloads_and_saves(self):
        app = self.app()
        self.fill(app)
        self.widget(app, "multiselect", "ReportedRoadType").set_value(["Chaussée", "Trottoir"])
        self.widget(app, "multiselect", "ReportedSurfaceType").set_value(["Enrobé", "Pavé"])
        self.widget(app, "multiselect", "RoadImpact").set_value(["Alternat par feu", "Travaux sur trottoir"])
        next(b for b in app.button if b.label == "Créer la demande").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        saved = data.load_store()["demandes"][0]
        self.assertIsNone(saved["MeterReference"])
        app = self.app(saved, mobile=False)
        for field in MULTIPLE_FIELDS:
            self.assertEqual(self.widget(app, "multiselect", field).value, saved[field])
        self.widget(app, "text_input", "MeterReference").set_value("000012")
        next(b for b in app.button if b.label == "Enregistrer les modifications").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(data.load_store()["demandes"][0]["MeterReference"], "000012")

    def test_other_visibility_and_meter_requirement_toggle(self):
        app = self.app()
        self.fill(app)
        self.assertFalse(any(w.key.endswith("_ReportedRoadTypeOther") for w in app.text_input))
        self.widget(app, "multiselect", "ReportedRoadType").set_value(["Autre", "Chaussée"]).run()
        self.assertTrue(self.widget(app, "text_input", "ReportedRoadTypeOther").label.endswith(" *"))
        next(b for b in app.button if b.label == "Créer la demande").click().run()
        self.assertIn("Précisez", app.error[0].value)
        self.widget(app, "text_input", "ReportedRoadTypeOther").set_value("Voie privée").run()
        self.widget(app, "multiselect", "ReportedRoadType").set_value(["Chaussée"]).run()
        self.assertFalse(any(w.key.endswith("_ReportedRoadTypeOther") for w in app.text_input))
        self.widget(app, "multiselect", "ReportedRoadType").set_value(["Autre"]).run()
        self.assertEqual(self.widget(app, "text_input", "ReportedRoadTypeOther").value, "Voie privée")
        self.widget(app, "multiselect", "ReportedRoadType").set_value(["Chaussée"]).run()
        self.widget(app, "selectbox", "RequestReason").set_value("Renouvellement de branchement").run()
        self.assertTrue(any("Matricule Compteur obligatoire" in c.value for c in app.caption))
        next(b for b in app.button if b.label == "Créer la demande").click().run()
        self.assertIn("Matricule Compteur", app.error[0].value)
        self.widget(app, "selectbox", "RequestReason").set_value("Sondage").run()
        self.assertEqual(self.widget(app, "text_input", "MeterReference").label, "Matricule Compteur")
        next(b for b in app.button if b.label == "Créer la demande").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertIsNone(data.load_store()["demandes"][0]["MeterReference"])

    def test_meter_text_survives_reason_changes(self):
        app = self.app()
        self.fill(app)
        self.widget(app, "text_input", "MeterReference").set_value("000567").run()
        self.widget(app, "selectbox", "RequestReason").set_value("Renouvellement de branchement").run()
        self.assertEqual(self.widget(app, "text_input", "MeterReference").value, "000567")
        self.widget(app, "selectbox", "RequestReason").set_value("Sondage").run()
        self.assertEqual(self.widget(app, "text_input", "MeterReference").value, "000567")

    def test_request_dialog_restores_choices_and_precision_after_photos(self):
        import streamlit as st
        script = '''
from components.dossier_forms import record_dialog
record_dialog("demandes", None)
'''
        app = AppTest.from_string(script)
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "email": "agent@example.test"}
        app.run()
        self.fill(app)
        self.widget(app, "multiselect", "ReportedRoadType").set_value(["Autre", "Trottoir"]).run()
        self.widget(app, "text_input", "ReportedRoadTypeOther").set_value("Voie privée").run()
        self.widget(app, "text_input", "MeterReference").set_value("000567").run()
        rerun = st.rerun
        with patch("streamlit.rerun", side_effect=lambda **kwargs: rerun()):
            next(b for b in app.button if b.label == "Ajouter une photo").click().run()
            self.assertFalse(app.exception)
            # AppTest ne nettoie pas l'arbre d'un fragment comme le navigateur.
            state = app.session_state.filtered_state
            app = AppTest.from_string(script)
            for key, value in state.items():
                app.session_state[key] = value
            app.run()
            next(b for b in app.button if b.label == "Terminer").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.widget(app, "multiselect", "ReportedRoadType").value, ["Autre", "Trottoir"])
        self.assertEqual(self.widget(app, "text_input", "ReportedRoadTypeOther").value, "Voie privée")
        self.assertEqual(self.widget(app, "text_input", "MeterReference").value, "000567")

    def test_historical_value_is_visible_but_not_an_option(self):
        old = self.request()
        old.pop("MeterReference")
        old.pop("ReportedRoadTypeOther")
        old.update(RequestReason="Ancien motif", ReportedRoadType="Communale", RoadImpact=True)
        app = self.app(old)
        self.assertFalse(app.exception)
        self.assertTrue(any("Ancien motif" in c.value for c in app.caption))
        self.assertNotIn("Ancien motif", self.widget(app, "selectbox", "RequestReason").options)
        self.assertEqual(self.widget(app, "multiselect", "ReportedRoadType").value, [])
        self.assertEqual(self.widget(app, "text_input", "MeterReference").value, "")

    def test_address_picker_and_service_prefill_keep_existing_paths(self):
        app = self.app()
        with patch("components.address_fields._picker", return_value={"address": "Rue Test", "city": "Test", "latitude": 45.5, "longitude": 4.3}):
            for field, value in valid_choices().items():
                self.widget(app, "multiselect" if field in MULTIPLE_FIELDS else "selectbox", field).set_value(value)
            next(b for b in app.button if b.label == "Créer la demande").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        saved = data.load_store()["demandes"][0]
        self.assertEqual(saved["LocationLandmark"], "45.500000, 4.300000")
        order = edits.save_record("interventions", dict(edits.new_record("interventions", saved), WorkOrderReferenceSaur="SAUR"))
        app = AppTest.from_string('''
import streamlit as st
from components.dossier_forms import render_record_form
render_record_form("prestations", st.session_state.request["RequestReference"],
                   parent=st.session_state.order, request=st.session_state.request)
''')
        app.session_state["request"] = dict(saved, ReportedRoadType=["Chaussée", "Trottoir"], ReportedSurfaceType=["Enrobé", "Pavé"])
        app.session_state["order"] = order
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(self.widget(app, "text_input", "RoadType").value, "Chaussée, Trottoir")
        self.assertEqual(self.widget(app, "text_input", "SurfaceRepairType").value, "Enrobé, Pavé")
