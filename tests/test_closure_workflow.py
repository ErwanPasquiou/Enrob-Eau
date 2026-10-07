from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from services import dossier_edit_service as edits
from services.business_data_service import load_store
from request_fixtures import valid_choices


class ClosureWorkflowTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        for table in ("demandes", "interventions", "prestations"):
            (root / f"{table}.json").write_text("[]", encoding="utf-8")
        patcher = patch("services.business_data_service.DATA_DIR", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        row = edits.new_record("demandes")
        row.update(valid_choices(), ReportedCity="Test", RequesterReference="agent@example.test")
        self.request = edits.save_record("demandes", row)

    def order(self, reference):
        row = edits.new_record("interventions", self.request)
        row["WorkOrderReferenceSaur"] = reference
        return edits.save_record("interventions", row)

    def service(self, order):
        row = edits.new_record("prestations", order)
        row.update(WorkReason="Réfection", WorkCity="Test")
        return edits.save_record("prestations", row)

    def finish(self, row, date="2026-09-29"):
        return edits.save_record("prestations", dict(row, ServiceStatus="Terminée", FinalRepairDate=date), row)

    def test_last_service_then_last_order_close_parents(self):
        one, two = self.order("SAUR-1"), self.order("SAUR-2")
        a, b, c = self.service(one), self.service(one), self.service(two)
        self.finish(a, "2026-09-27")
        self.assertEqual(load_store()["interventions"][0]["WorkOrderStatus"], "En cours")
        self.finish(b, "2026-09-28")
        store = load_store()
        self.assertEqual(store["interventions"][0]["ClosedAt"], "2026-09-28T00:00:00")
        self.assertNotEqual(store["demandes"][0]["RequestStatus"], "Clôturée")
        self.finish(c)
        store = load_store()
        self.assertTrue(all(r["WorkOrderStatus"] == "Clôturée" for r in store["interventions"]))
        self.assertEqual(store["demandes"][0]["RequestStatus"], "Clôturée")

    def test_saur_reference_required_unique_and_editable(self):
        row = edits.new_record("interventions", self.request)
        self.assertTrue(row["WorkOrderReferenceEnrobEau"].startswith("INT-"))
        self.assertIsNone(row["WorkOrderReferenceSaur"])
        self.assertIsNone(row["IssuedAt"])
        with self.assertRaisesRegex(ValueError, "obligatoire"):
            edits.save_record("interventions", row)
        order = self.order(" SAUR-1 ")
        self.assertEqual(order["WorkOrderReferenceSaur"], "SAUR-1")
        with self.assertRaisesRegex(ValueError, "existe déjà"):
            self.order("SAUR-1")
        with self.assertRaises(ValueError):
            edits.save_record("interventions", dict(order, WorkOrderReferenceEnrobEau="SAUR-2"), order)
        updated = edits.save_record("interventions", dict(order, WorkOrderReferenceSaur="SAUR-2"), order)
        self.assertEqual(updated["WorkOrderReferenceEnrobEau"], order["WorkOrderReferenceEnrobEau"])
        self.assertEqual(updated["WorkOrderReferenceSaur"], "SAUR-2")

    def test_date_alone_closes_and_dict_dates_are_optional(self):
        order = self.order("SAUR-1")
        saved = edits.save_record("interventions", dict(order, ClosedAt="2026-09-29T15:45:00"), order)
        self.assertEqual(saved["WorkOrderStatus"], "Clôturée")
        self.assertEqual(saved["ClosedAt"], "2026-09-29T00:00:00")
        self.assertEqual(load_store()["demandes"][0]["RequestStatus"], "Clôturée")

    def test_empty_children_do_not_close_and_refusal_is_preserved(self):
        order = self.order("SAUR-1")
        store = load_store()
        self.assertNotEqual(store["demandes"][0]["RequestStatus"], "Clôturée")
        self.assertNotEqual(store["interventions"][0]["WorkOrderStatus"], "Clôturée")
        service = self.service(order)
        edits.change_request_status(store["demandes"][0], "Refusée", "Décision")
        self.finish(service)
        self.assertEqual(load_store()["demandes"][0]["RequestStatus"], "Refusée")

    def test_failed_cascade_write_restores_all_tables(self):
        order = self.order("SAUR-1")
        service = self.service(order)
        before = deepcopy(load_store())
        write = edits._write_table
        failed = False

        def fail_once(table, rows):
            nonlocal failed
            if table == "prestations" and not failed:
                failed = True
                raise OSError("Échec simulé")
            return write(table, rows)

        with patch.object(edits, "_write_table", side_effect=fail_once):
            with self.assertRaises(OSError):
                self.finish(service)
        self.assertEqual(load_store(), before)

    def test_delete_last_open_child_closes_remaining_group(self):
        order = self.order("SAUR-1")
        done, pending = self.service(order), self.service(order)
        self.finish(done)
        edits.delete_record("prestations", pending)
        self.assertEqual(load_store()["demandes"][0]["RequestStatus"], "Clôturée")

    def test_form_reference_date_and_no_time_inputs(self):
        script = '''
from components.dossier_forms import render_record_form
render_record_form("interventions", "REQ-test", parent={"RequestReference": "REQ-test"})
'''
        app = AppTest.from_string(script).run()
        self.assertEqual(len(app.exception), 0)
        reference = next(w for w in app.text_input if "SI SAUR" in w.label)
        self.assertEqual(reference.value, "")
        self.assertFalse(reference.disabled)
        self.assertEqual(len(app.time_input), 0)
        self.assertTrue(any("Suivi de la DICT" in m.value for m in app.markdown))
        from datetime import date
        next(w for w in app.date_input if w.key.endswith("_ClosedAt")).set_value(date(2026, 9, 29)).run()
        self.assertTrue(any(w.value == "Clôturée" and w.disabled for w in app.text_input))

    def test_refused_request_has_red_stage_in_list_and_detail(self):
        edits.change_request_status(self.request, "Refusée", "Refus de la demande")
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages/gestion_des_dossiers.py"))
        app.session_state["current_user"] = {"actif": True, "profil": "agent", "email": "agent@example.test"}
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        progress = [node.proto.body for node in app.get("html") if 'aria-label="Avancement du dossier"' in node.proto.body]
        self.assertEqual(len(progress), 2)
        self.assertTrue(all('stage-dot refused' in html and 'Demande : Refusée' in html for html in progress))
