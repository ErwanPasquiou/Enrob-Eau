import unittest
from services.business_data_service import load_store
from services.home_service import home_data, coordinates


class HomeDataTests(unittest.TestCase):
    def test_map_uses_request_coordinates_without_service(self):
        store = load_store()
        order = next(r for r in store["interventions"] if r["WorkOrderStatus"] == "En cours")
        request = next(r for r in store["demandes"] if r["RequestReference"] == order["RequestReference"])
        store["prestations"] = []
        request["LocationLandmark"] = "45.528, 4.373"
        _, locations = home_data(store)
        point = locations.loc[locations["Référence"] == order["WorkOrderReferenceSaur"]].iloc[0]
        self.assertEqual((point.latitude, point.longitude), (45.528, 4.373))

    def test_counts_and_map_follow_test_files(self):
        data, locations = home_data(load_store())
        self.assertEqual({key: len(frame) for key, frame in data.items()}, {
            "demandes-attente": 4, "interventions-cours": 5,
            "prestations-cours": 5, "prestations-refection": 5,
        })
        # Les cinq interventions actives des exemples ont désormais une prestation géolocalisée.
        self.assertEqual(locations["Référence"].nunique(), 5)
        self.assertEqual(len(locations), 5)
        self.assertTrue(set(locations["Référence"]) <= set(data["interventions-cours"]["Référence"]))

    def test_changes_in_files_drive_categories(self):
        store = load_store()
        service = next(r for r in store["prestations"] if r["ServiceStatus"] == "En cours")
        service["FinalRepairDate"] = "2026-09-28"
        data, _ = home_data(store)
        self.assertEqual(len(data["prestations-cours"]), 4)
        self.assertEqual(len(data["prestations-refection"]), 4)

    def test_empty_tables_keep_display_columns(self):
        data, locations = home_data(dict(demandes=[], interventions=[], prestations=[]))
        self.assertTrue(all(frame.empty for frame in data.values()))
        self.assertIn("latitude", locations.columns)

    def test_invalid_coordinates_are_not_mapped(self):
        for value in (None, "", "nan,4", "91,4", "45,181", "invalide", "45,4,2"):
            self.assertIsNone(coordinates(value))
        self.assertEqual(coordinates("45.528,4.373"), (45.528, 4.373))


if __name__ == "__main__":
    unittest.main()
