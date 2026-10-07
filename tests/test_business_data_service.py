import csv
import io
import unittest
from datetime import date

from services.business_data_service import load_store, filter_store, related_records, table_frame, export_csv
from services.data_model import SCHEMAS


class BusinessDataTests(unittest.TestCase):
    def setUp(self):
        self.store = load_store()

    def test_files_match_model_and_load_independently(self):
        for table, columns in SCHEMAS.items():
            self.assertTrue(self.store[table])
            self.assertTrue(all(set(row) == set(columns) for row in self.store[table]))
        other = load_store()
        self.store["demandes"][0]["RequestComment"] = "Changed"
        self.assertNotEqual(other["demandes"][0]["RequestComment"], "Changed")

    def test_global_filters_propagate_to_children(self):
        filtered = filter_store(self.store, cities=["Saint-Chamond"], period=(date(2026, 9, 1), date(2026, 9, 1)))
        self.assertEqual([r["RequestReference"] for r in filtered["demandes"]], ["DEM-000001"])
        self.assertEqual(len(filtered["interventions"]), 2)
        self.assertEqual(len(filtered["prestations"]), 3)
        self.assertEqual(filtered["prestations"], related_records(self.store, "DEM-000001")["prestations"])

    def test_linked_search_selects_whole_dossier(self):
        filtered = filter_store(self.store, query="PR-000002")
        self.assertEqual(len(filtered["demandes"]), 1)
        self.assertEqual(len(filtered["prestations"]), 3)
        self.assertFalse(filter_store(self.store, query="absent-999")["demandes"])

    def test_export_column_order_utf8_and_more_than_preview(self):
        store = {"demandes": self.store["demandes"] * 100}
        frame = table_frame(store, "demandes", ["RequestComment", "RequestReference"])
        self.assertEqual(len(frame.head(1000)), 1000)
        data = export_csv(frame)
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[0], ["RequestComment", "RequestReference"])
        self.assertEqual(len(rows) - 1, 1200)

    def test_empty_result_keeps_headers_and_formula_is_escaped(self):
        filtered = filter_store(self.store, query="absent-999")
        frame = table_frame(filtered, "prestations", ["ServiceReference"])
        self.assertEqual(export_csv(frame).decode("utf-8-sig"), "ServiceReference\n")
        self.store["demandes"][0]["RequestComment"] = '=HYPERLINK("x")'
        frame = table_frame(self.store, "demandes", ["RequestComment"])
        first = next(csv.DictReader(io.StringIO(export_csv(frame).decode("utf-8-sig")), delimiter=";"))
        self.assertTrue(first["RequestComment"].startswith("'="))


if __name__ == "__main__":
    unittest.main()
