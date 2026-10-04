import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.business_data_service import load_store
from services.dossier_edit_service import new_record, save_record, change_request_status, delete_record


class DossierEditTests(unittest.TestCase):
    def test_dates_follow_backfill_or_manual_choice(self):
        order = next(r for r in self.source["interventions"] if r["WorkOrderStatus"] == "En cours")
        row = new_record("prestations", order)
        row.update(WorkReason="Test", WorkCity="Test", BackfillDate="2026-09-20",
                   HasConcrete2Cm=True, HasTemporaryRepair=True)
        saved = save_record("prestations", row)
        self.assertEqual(saved["Concrete2CmDate"], "2026-09-20")
        self.assertEqual(saved["TemporaryRepairDate"], "2026-09-20")
        manual = dict(saved, HasTemporaryRepair=False, TemporaryRepairDate="2026-09-22")
        saved = save_record("prestations", manual, saved)
        self.assertEqual(saved["TemporaryRepairDate"], "2026-09-22")
        with self.assertRaisesRegex(ValueError, "manuellement"):
            save_record("prestations", dict(saved, TemporaryRepairDate=None), saved)

    def setUp(self):
        self.source = load_store()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        for table, rows in self.source.items():
            (root / f"{table}.json").write_text(json.dumps(rows), encoding="utf-8")
        patcher = patch("services.business_data_service.DATA_DIR", root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_delete_service_then_childless_order(self):
        order = next(r for r in self.source["interventions"] if r["WorkOrderReferenceEnrobEau"] == "WO-1-1")
        with self.assertRaisesRegex(ValueError, "possède des prestations"):
            delete_record("interventions", order)
        children = [r for r in load_store()["prestations"] if r["WorkOrderReferenceEnrobEau"] == order["WorkOrderReferenceEnrobEau"]]
        for child in children:
            delete_record("prestations", child)
        latest_order = next(r for r in load_store()["interventions"] if r["WorkOrderReferenceEnrobEau"] == order["WorkOrderReferenceEnrobEau"])
        delete_record("interventions", latest_order)
        self.assertNotIn(order, load_store()["interventions"])
        self.assertTrue(any(r["WorkOrderReferenceEnrobEau"] == "WO-1-2" for r in load_store()["interventions"]))

    def test_delete_checks_latest_children_and_stale_rows(self):
        order = next(r for r in self.source["interventions"] if r["WorkOrderReferenceEnrobEau"] == "WO-4-1")
        child = new_record("prestations", order)
        child.update(WorkReason="Test", WorkCity="Saint-Héand")
        save_record("prestations", child)
        with self.assertRaises(ValueError):
            delete_record("interventions", order)
        with self.assertRaises(ValueError):
            delete_record("prestations", dict(load_store()["prestations"][0], Comment="Ancienne valeur"))

    def test_request_email_and_dict_options(self):
        request = new_record("demandes")
        request.update(RequestReason="Fuite", ReportedCity="Saint-Héand", RequesterReference="agent@example.test")
        self.assertEqual(request["DictAtuIndicator"], "NA")
        saved = save_record("demandes", request)
        with self.assertRaisesRegex(ValueError, "DICT"):
            save_record("demandes", dict(saved, DictAtuIndicator=True), saved)
        with self.assertRaisesRegex(ValueError, "e-mail"):
            save_record("demandes", dict(saved, RequesterReference="agent"), saved)

    def test_create_intervention_then_service_and_reload(self):
        request = next(r for r in self.source["demandes"] if r["RequestStatus"] == "À traiter")
        order = save_record("interventions", dict(new_record("interventions", request), WorkOrderReferenceSaur="SAUR-TEST-001"))
        service = new_record("prestations", order)
        service.update(WorkReason="Réfection", WorkCity=request["ReportedCity"])
        saved = save_record("prestations", service)
        store = load_store()
        self.assertIn(saved, store["prestations"])
        self.assertEqual(saved["WorkOrderReferenceEnrobEau"], order["WorkOrderReferenceEnrobEau"])
        self.assertEqual(order["RequestReference"], request["RequestReference"])

    def test_reason_required_and_resume_unlocks_creation(self):
        request = self.source["demandes"][0]
        with self.assertRaises(ValueError):
            change_request_status(request, "Refusée")
        waiting = change_request_status(request, "En attente", "Attente accord commune")
        self.assertIn("Attente accord commune", waiting["RequestComment"])
        with self.assertRaises(ValueError):
            save_record("interventions", dict(new_record("interventions", waiting), WorkOrderReferenceSaur="SAUR-TEST-002"))
        resumed = change_request_status(waiting, "En cours")
        save_record("interventions", dict(new_record("interventions", resumed), WorkOrderReferenceSaur="SAUR-TEST-002"))

    def test_stale_edit_does_not_overwrite_saved_change(self):
        original = self.source["demandes"][0]
        first = dict(original, CustomerName="Premier changement")
        save_record("demandes", first, original)
        with self.assertRaisesRegex(ValueError, "a changé"):
            save_record("demandes", dict(original, CustomerName="Écrasement"), original)
        self.assertEqual(load_store()["demandes"][0]["CustomerName"], "Premier changement")

    def test_invalid_service_is_not_written(self):
        order = next(r for r in self.source["interventions"] if r["WorkOrderStatus"] == "En cours")
        service = new_record("prestations", order)
        service.update(WorkReason="Réfection", WorkCity="Saint-Héand", HasTemporaryRepair=True)
        with self.assertRaises(ValueError):
            save_record("prestations", service)
        self.assertEqual(len(load_store()["prestations"]), len(self.source["prestations"]))


if __name__ == "__main__":
    unittest.main()
