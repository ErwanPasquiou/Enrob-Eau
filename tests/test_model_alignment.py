from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services import business_data_service as data
from services import dossier_edit_service as edits
from services.data_model import SCHEMAS
from services.home_service import home_data
from services.local_model_migration import adapt_store, migrate_local_data
from services.refection_service import prestation_rows, filter_prestations


ROOT = Path(__file__).resolve().parents[1]


class LocalDataCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for table in SCHEMAS:
            (self.root / f"{table}.json").write_text("[]", encoding="utf-8")
        patcher = patch.object(data, "DATA_DIR", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        request = edits.new_record("demandes")
        request.update(RequestReason="Travaux", ReportedCity="Test", RequesterReference="agent@example.test",
                       LocationLandmark="45.5,4.3")
        self.request = edits.save_record("demandes", request)

    def order(self, reference="SAUR-001"):
        row = edits.new_record("interventions", self.request)
        row["WorkOrderReferenceSaur"] = reference
        return edits.save_record("interventions", row)

    def service(self, order):
        row = edits.new_record("prestations", order)
        row.update(WorkReason="Réfection", WorkCity="Test", WorkCoordinates="45.6,4.4")
        return edits.save_record("prestations", row)

    def write(self, store):
        for table, rows in store.items():
            (self.root / f"{table}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def contents(self):
        return {table: (self.root / f"{table}.json").read_bytes() for table in SCHEMAS}


class ModelAlignmentTests(LocalDataCase):
    def test_rename_preserves_identity_services_photos_and_projections(self):
        from services import photo_service as photos
        from test_photo_service import image_bytes

        order = self.order()
        service = self.service(order)
        photo = photos.prepare_photo("test.png", image_bytes(), photo_name="Travaux")
        photos.add_photos("prestations", service["ServiceReference"], [photo], "agent@example.test")
        service_bytes = self.contents()["prestations"]
        updated = edits.save_record("interventions", dict(order, WorkOrderReferenceSaur="SAUR-NOUVELLE"), order)
        self.assertEqual(updated["WorkOrderReferenceEnrobEau"], order["WorkOrderReferenceEnrobEau"])
        self.assertEqual(updated["CreatedAt"], order["CreatedAt"])
        self.assertEqual(self.contents()["prestations"], service_bytes)
        self.assertEqual(service["WorkOrderReferenceEnrobEau"], updated["WorkOrderReferenceEnrobEau"])
        store = data.load_store()
        self.assertEqual(data.related_records(store, self.request["RequestReference"])["prestations"], [service])
        self.assertEqual(data.filter_store(store, query="SAUR-NOUVELLE")["prestations"], [service])
        projection = filter_prestations(prestation_rows(store), query="SAUR-NOUVELLE")
        self.assertEqual([r["ServiceReference"] for r in projection], [service["ServiceReference"]])
        self.assertNotIn("WorkOrderReferenceSaur", store["prestations"][0])
        self.assertEqual(len(photos.list_photos("prestations", service["ServiceReference"])), 1)
        indicators, locations = home_data(store)
        self.assertEqual(list(indicators["interventions-cours"]["Référence"]), ["SAUR-NOUVELLE"])
        self.assertEqual(list(locations["Référence"]), ["SAUR-NOUVELLE"])
        self.assertEqual(len(locations), 1)  # Pas de second point issu de la demande.
        export = data.export_csv(data.table_frame(store, "interventions")).decode("utf-8-sig")
        self.assertIn("WorkOrderReferenceEnrobEau;WorkOrderReferenceSaur;RequestReference", export)
        self.assertIn("SAUR-NOUVELLE", export)
        self.assertNotIn("WorkOrderReferenceSaur", data.table_frame(store, "prestations").columns)
        changed_service = edits.save_record("prestations", dict(service, WorkReason="Après renommage"), service)
        self.assertEqual(changed_service["WorkOrderReferenceEnrobEau"], order["WorkOrderReferenceEnrobEau"])
        # La clôture ascendante suit la même identité après le renommage.
        edits.save_record("prestations", dict(changed_service, ServiceStatus="Terminée", FinalRepairDate="2026-10-03"), changed_service)
        self.assertEqual(data.load_store()["demandes"][0]["RequestStatus"], "Clôturée")

    def test_saur_uniqueness_edit_self_stale_edit_and_immutable_links(self):
        first, second = self.order(), self.order("SAUR-002")
        unchanged = edits.save_record("interventions", first, first)
        self.assertEqual(unchanged["WorkOrderReferenceSaur"], first["WorkOrderReferenceSaur"])
        for reference in ("", "   ", " SAUR-002 "):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                edits.save_record("interventions", dict(unchanged, WorkOrderReferenceSaur=reference), unchanged)
        with self.assertRaisesRegex(ValueError, "existe déjà"):
            self.order(" SAUR-002 ")
        with self.assertRaisesRegex(ValueError, "a changé"):
            edits.save_record("interventions", dict(first, WorkOrderReferenceSaur="NOUVEAU"), first)
        for changes in ({"WorkOrderReferenceEnrobEau": second["WorkOrderReferenceEnrobEau"]}, {"RequestReference": "AUTRE"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                edits.save_record("interventions", dict(unchanged, **changes), unchanged)
        service = self.service(unchanged)
        with self.assertRaisesRegex(ValueError, "liens"):
            edits.save_record("prestations", dict(service, WorkOrderReferenceEnrobEau=second["WorkOrderReferenceEnrobEau"]), service)

    def test_missing_parents_and_duplicate_saur_are_detected_at_load(self):
        first, second = self.order(), self.order("SAUR-002")
        self.service(first)
        valid = data.load_store()
        cases = [
            ("interventions", "RequestReference", "ABSENT", "demande inexistante"),
            ("prestations", "WorkOrderReferenceEnrobEau", "ABSENT", "intervention inexistante"),
            ("interventions", "WorkOrderReferenceSaur", second["WorkOrderReferenceSaur"], "dupliquée"),
            ("interventions", "WorkOrderReferenceSaur", None, "obligatoire"),
        ]
        for table, field, value, error in cases:
            with self.subTest(field=field, value=value):
                bad = deepcopy(valid)
                bad[table][0][field] = value
                self.write(bad)
                with self.assertRaisesRegex(ValueError, error):
                    data.load_store()
        self.write(valid)

    def test_creation_restrictions_still_apply_in_service(self):
        order = self.order()
        for status in ("En attente", "Clôturée"):
            store = data.load_store()
            store["interventions"][0]["WorkOrderStatus"] = status
            self.write(store)
            with self.assertRaisesRegex(ValueError, "Réactivez"):
                self.service(order)
        store["interventions"][0]["WorkOrderStatus"] = "En cours"
        for status in edits.BLOCKED_REQUESTS:
            store["demandes"][0]["RequestStatus"] = status
            self.write(store)
            with self.assertRaisesRegex(ValueError, "Reprenez"):
                self.service(order)

    def test_single_entry_and_choice_of_parent_then_edit_saur_in_ui(self):
        first, second = self.order(), self.order("SAUR-002")
        app = AppTest.from_file(str(ROOT / "pages/gestion_des_dossiers.py"))
        app.session_state["current_user"] = {"actif": True, "profil": "administrateur", "email": "agent@example.test"}
        app.run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len([b for b in app.button if "Créer une prestation" in b.label]), 1)
        self.assertFalse(any(b.key and b.key.startswith("add_service_") for b in app.button))
        self.assertEqual({e.label for e in app.expander if e.label.startswith("SAUR-")}, {"SAUR-001", "SAUR-002"})
        next(b for b in app.button if b.label == "Créer une prestation").click().run()
        selection = next(s for s in app.selectbox if s.label == "Intervention concernée *")
        self.assertEqual(selection.options, ["SAUR-001", "SAUR-002"])
        # AppTest 1.38 relance tout le script lors d'un changement de widget
        # dans un dialogue. Appeler le dialogue directement pour ses relances.
        app = AppTest.from_string('''
import streamlit as st
from components.dossier_forms import create_service_dialog
if not st.session_state.get("dossier_saved_ref"):
    create_service_dialog(st.session_state.request, st.session_state.orders)
''')
        app.session_state["request"] = self.request
        app.session_state["orders"] = [first, second]
        app.session_state["current_user"] = {"actif": True, "profil": "administrateur", "email": "agent@example.test"}
        app.run()
        selection = next(s for s in app.selectbox if s.label == "Intervention concernée *")
        selection.set_value(second["WorkOrderReferenceEnrobEau"]).run()
        next(b for b in app.button if b.label == "Créer la prestation").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(data.load_store()["prestations"][0]["WorkOrderReferenceEnrobEau"], second["WorkOrderReferenceEnrobEau"])
        app = AppTest.from_string('''
import streamlit as st
from components.dossier_forms import render_record_form
if not st.session_state.get("dossier_saved_ref"):
    render_record_form("interventions", st.session_state.original["RequestReference"], original=st.session_state.original)
''')
        app.session_state["original"] = first
        app.run()
        reference = next(w for w in app.text_input if "SI SAUR" in w.label)
        self.assertFalse(reference.disabled)
        reference.set_value("SAUR-CORRIGEE")
        next(b for b in app.button if b.label == "Enregistrer les modifications").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(data.load_store()["interventions"][0]["WorkOrderReferenceSaur"], "SAUR-CORRIGEE")

    def test_demandes_label_and_mes_demandes_are_visible_without_route_change(self):
        from services.access_service import PAGES
        self.assertIn(("forms", "Demandes", "pages/forms.py", "forms"), PAGES)
        app = AppTest.from_file(str(ROOT / "pages/forms.py"))
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "email": "agent@example.test"}
        app.run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Mes demandes")
        header = next(node.proto.body for node in app.get("html") if 'class="enrobeau-header"' in node.proto.body)
        self.assertIn('aria-current="page">Demandes</a>', header)
        self.assertNotIn("Forms", header)


class LocalMigrationTests(LocalDataCase):
    def legacy(self):
        order = self.order()
        self.service(order)
        store = data.load_store()
        # Ancienne référence unique servant simultanément de clé et de valeur métier.
        for row in store["interventions"]:
            row["WorkOrderReference"] = row.pop("WorkOrderReferenceEnrobEau")
            row.pop("WorkOrderReferenceSaur")
        for row in store["prestations"]:
            row["WorkOrderReference"] = row.pop("WorkOrderReferenceEnrobEau")
        return store

    def test_migration_preserves_all_values_links_and_original_backup(self):
        legacy = self.legacy()
        self.write(legacy)
        original_bytes = self.contents()
        preview = migrate_local_data()
        self.assertEqual(preview["changed"], ["interventions", "prestations"])
        self.assertEqual(self.contents(), original_bytes)
        self.assertFalse((self.root / "backups").exists())
        with self.assertRaisesRegex(ValueError, "CODEX-001"):
            data.load_store()
        result = migrate_local_data(apply=True)
        target = data.load_store()
        self.assertEqual(target["demandes"], legacy["demandes"])
        self.assertEqual(self.contents()["demandes"], original_bytes["demandes"])
        for table in ("interventions", "prestations"):
            for old, new in zip(legacy[table], target[table]):
                restored = dict(new)
                self.assertEqual(restored.pop("WorkOrderReferenceEnrobEau"), old["WorkOrderReference"])
                if table == "interventions":
                    self.assertEqual(restored.pop("WorkOrderReferenceSaur"), old["WorkOrderReference"])
                self.assertEqual(restored, {k: v for k, v in old.items() if k != "WorkOrderReference"})
        for table, content in original_bytes.items():
            self.assertEqual((Path(result["backup"]) / f"{table}.json").read_bytes(), content)
        migrated_bytes = self.contents()
        self.assertEqual(migrate_local_data(apply=True)["changed"], [])
        self.assertEqual(self.contents(), migrated_bytes)

    def test_incoherent_sources_are_rejected_without_writes(self):
        legacy = self.legacy()
        orphan = deepcopy(legacy)
        orphan["prestations"][0]["WorkOrderReference"] = "ABSENT"
        duplicate = deepcopy(legacy)
        duplicate["interventions"].append(deepcopy(duplicate["interventions"][0]))
        blank = deepcopy(legacy)
        blank["interventions"][0]["WorkOrderReference"] = ""
        mixed = deepcopy(legacy)
        mixed["interventions"] = adapt_store(legacy)["interventions"]
        ambiguous = deepcopy(legacy)
        ambiguous["interventions"][0]["WorkOrderReferenceSaur"] = "autre"
        for source in (orphan, duplicate, blank, mixed, ambiguous):
            with self.subTest(source=source):
                self.write(source)
                before = self.contents()
                with self.assertRaises(ValueError):
                    migrate_local_data(apply=True)
                self.assertEqual(self.contents(), before)
                self.assertFalse((self.root / "backups").exists())

    def test_write_failure_compensates_and_keeps_backup(self):
        legacy = self.legacy()
        self.write(legacy)
        real_write = edits._write_table

        def fail_second(table, rows):
            if table == "prestations":
                raise OSError("Disque indisponible")
            real_write(table, rows)

        with patch.object(edits, "_write_table", side_effect=fail_second), self.assertRaisesRegex(OSError, "sauvegarde"):
            migrate_local_data(apply=True)
        for table, content in self.contents().items():
            self.assertEqual(json.loads(content), legacy[table])
        self.assertEqual(len(list((self.root / "backups").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
