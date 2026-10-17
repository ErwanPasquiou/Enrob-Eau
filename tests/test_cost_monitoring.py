from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from services import cost_monitoring_service as finops


ROOT = Path(__file__).resolve().parents[1]
ADMIN = dict(email="admin@example.test", prenom="Test", nom="Admin", actif=True, profil="administrateur")
SETTINGS = dict(app_id="test-app", warehouse_id="test-warehouse", app_rate="1", sql_rate="", dedicated=False)
COLUMNS = ["composant", "jour", "sku", "unite", "consommation", "derniere_consommation", "derniere_ingestion"]


def usage_frame():
    return pd.DataFrame([
        ["application", date(2026, 10, 1), "APP_SKU", "DBU", Decimal("12"), datetime(2026, 10, 2), date(2026, 10, 2)],
        ["warehouse", date(2026, 10, 1), "SQL_SKU", "DBU", Decimal("20"), datetime(2026, 10, 2), date(2026, 10, 2)],
    ], columns=COLUMNS)


class CostCalculationTests(unittest.TestCase):
    def test_shared_warehouse_never_increases_app_amount(self):
        summary = finops.summarize_usage(usage_frame(), "1", "0.75")
        self.assertEqual(summary["application"]["cost"], Decimal("12"))
        self.assertEqual(summary["warehouse"]["cost"], Decimal("15"))
        self.assertEqual(summary["attributable"], Decimal("12"))

    def test_dedicated_total_requires_both_costs(self):
        self.assertEqual(finops.summarize_usage(usage_frame(), 1, "0,75", True)["attributable"], Decimal("27"))
        self.assertIsNone(finops.summarize_usage(usage_frame(), 1, "", True)["attributable"])
        self.assertIsNone(finops.summarize_usage(usage_frame().iloc[:1], 1, 1, True)["attributable"])

    def test_unknown_price_keeps_dbu_without_zero_cost(self):
        item = finops.summarize_usage(usage_frame(), 1, None)["warehouse"]
        self.assertEqual(item["dbu"], Decimal("20"))
        self.assertIsNone(item["cost"])

    def test_empty_period_is_not_free(self):
        summary = finops.summarize_usage(pd.DataFrame(columns=COLUMNS), 1, 1)
        self.assertIsNone(summary["application"]["dbu"])
        self.assertIsNone(summary["attributable"])

    def test_corrections_and_negative_net_are_preserved(self):
        frame = pd.concat([usage_frame().iloc[:1]] * 3, ignore_index=True)
        frame["consommation"] = [Decimal("12"), Decimal("-12"), Decimal("10.1")]
        self.assertEqual(finops.summarize_usage(frame, "0.75", None)["attributable"], Decimal("7.575"))
        frame["consommation"] = [Decimal("-12"), Decimal("0"), Decimal("0")]
        self.assertEqual(finops.summarize_usage(frame, 1, None)["attributable"], Decimal("-12"))

    def test_different_units_are_never_summed_or_priced_as_dbu(self):
        frame = pd.concat([usage_frame(), usage_frame().iloc[:1]], ignore_index=True)
        frame.loc[2, "unite"] = "GB"
        item = finops.summarize_usage(frame, 1, 1)["application"]
        self.assertTrue(item["unsupported_unit"])
        self.assertIsNone(item["cost"])

    def test_invalid_values_are_rejected_and_explicit_free_price_allowed(self):
        for value in ("-1", "NaN", "Infinity", "oops"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                finops.parse_rate(value)
        self.assertEqual(finops.summarize_usage(usage_frame(), 0, None)["attributable"], 0)
        frame = usage_frame()
        frame.loc[0, "consommation"] = None
        with self.assertRaises(ValueError):
            finops.summarize_usage(frame, 1, 1)


class MonitoringQueryTests(unittest.TestCase):
    def setUp(self):
        self.scope = finops.MonitoringScope("test-app", "test-warehouse", date(2026, 10, 1), date(2026, 10, 17))

    def test_scope_rejects_invalid_dates_and_sql_identifier(self):
        for scope in (
            finops.MonitoringScope("app' OR 1=1", "warehouse", self.scope.start, self.scope.end),
            finops.MonitoringScope("app", "warehouse", self.scope.end, self.scope.start),
            finops.MonitoringScope("app", "warehouse", date(2024, 1, 1), date(2025, 1, 1)),
            finops.MonitoringScope("app", "warehouse", self.scope.start, self.scope.end, "system.billing.usage;DROP"),
        ):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                scope.validate()

    def test_billing_query_binds_resources_and_retains_all_corrections(self):
        with patch.object(finops, "authorize_monitoring"), patch.object(finops, "_read", return_value=usage_frame()) as read:
            finops.load_usage(self.scope)
        query, parameters = read.call_args.args
        self.assertNotIn("test-app", query)
        self.assertNotIn("record_type", query)
        self.assertIn("SUM(usage_quantity)", query)
        self.assertIn("`system`.`billing`.`usage`", query)
        self.assertEqual(parameters, ["test-app", self.scope.start, self.scope.end, "test-app", "test-warehouse"])

    def test_sql_activity_uses_exclusive_next_day_boundary(self):
        with patch.object(finops, "authorize_monitoring"), patch.object(finops, "_read") as read:
            finops.load_sql_activity(self.scope)
        query, parameters = read.call_args.args
        self.assertIn("execution_duration_ms", query)
        self.assertEqual(parameters, ["test-warehouse", "2026-10-01T00:00:00Z", "2026-10-18T00:00:00Z"])

    def test_non_admin_and_fallback_never_query_billing_or_activity(self):
        with patch.object(finops, "get_connection") as connection:
            for method in (finops.load_usage, finops.load_sql_activity):
                with patch.object(finops, "require_admin", side_effect=PermissionError("Refusé")), self.assertRaises(PermissionError):
                    method(self.scope)
                with patch.object(finops, "require_admin", return_value=ADMIN), patch.object(finops, "is_local_mode", return_value=True), self.assertRaises(finops.MonitoringUnavailable):
                    method(self.scope)
            connection.assert_not_called()

    def test_connection_failure_is_not_an_empty_consumption(self):
        with patch.object(finops, "get_connection", side_effect=RuntimeError("secret connection details")), self.assertRaises(finops.MonitoringUnavailable) as caught:
            finops._read("SELECT 1", [])
        self.assertNotIn("secret", str(caught.exception))

    def test_connector_decimal_result_is_preserved(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.description = [("consommation",)]
        cursor.fetchall.return_value = [(Decimal("1.123456789"),)]
        with patch.object(finops, "get_connection", return_value=connection):
            result = finops._read("SELECT ?", [1])
        self.assertEqual(result.iloc[0, 0], Decimal("1.123456789"))
        cursor.execute.assert_called_once_with("SELECT ?", [1])


class MonitoringInterfaceTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.object(finops, "authorize_monitoring", return_value=ADMIN),
            patch("components.cost_monitoring._setting", side_effect=lambda name, default="": default),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = AppTest.from_file(str(ROOT / "pages/administration.py"))
        self.app.session_state["current_user"] = ADMIN.copy()
        self.app.session_state["admin_section"] = "Consommation et coûts"
        self.app.session_state["finops_settings"] = SETTINGS.copy()

    def test_monitoring_does_not_load_user_list_or_automatically_query_usage(self):
        with patch("components.administration_users.get_administration_users", side_effect=AssertionError("Users must stay independent")), patch.object(finops, "load_usage") as load:
            self.app.run()
        self.assertFalse(self.app.exception)
        load.assert_not_called()
        self.assertTrue(self.app.button(key="finops_refresh"))

    def test_refresh_displays_unknown_sql_price_and_caches_until_requested(self):
        with patch.object(finops, "load_usage", return_value=usage_frame()) as load:
            self.app.run().button(key="finops_refresh").click().run()
            self.assertFalse(self.app.exception)
            values = [metric.value for metric in self.app.metric]
            self.assertEqual(values, ["12,00 €", "Non disponible", "12,00 €"])
            self.app.run()
            load.assert_called_once()

    def test_changing_tariff_recalculates_without_querying(self):
        with patch.object(finops, "load_usage", return_value=usage_frame()) as load:
            self.app.run().button(key="finops_refresh").click().run()
            self.app.text_input[3].set_value("0,75")
            self.app.checkbox[0].check()
            self.app.button[0].click().run()
            self.assertFalse(self.app.exception)
            self.assertEqual([m.value for m in self.app.metric], ["12,00 €", "15,00 €", "27,00 €"])
            load.assert_called_once()

    def test_resource_and_period_changes_never_reuse_other_snapshot(self):
        with patch.object(finops, "load_usage", return_value=usage_frame()):
            self.app.run().button(key="finops_refresh").click().run()
            self.app.selectbox(key="finops_period").select("Mois précédent").run()
            self.assertFalse(self.app.metric)
            self.app.button(key="finops_refresh").click().run()
            self.app.text_input[0].set_value("other-app")
            self.app.button[0].click().run()
            self.assertFalse(self.app.metric)

    def test_refresh_failure_removes_old_metrics(self):
        with patch.object(finops, "load_usage", side_effect=[usage_frame(), finops.MonitoringUnavailable("Accès indisponible")]):
            self.app.run().button(key="finops_refresh").click().run()
            self.app.button(key="finops_refresh").click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.metric)
        self.assertTrue(self.app.error)

    def test_lost_permission_hides_cached_data(self):
        with patch.object(finops, "load_usage", return_value=usage_frame()):
            self.app.run().button(key="finops_refresh").click().run()
        with patch.object(finops, "authorize_monitoring", side_effect=PermissionError("Droits retirés")):
            self.app.run()
        self.assertFalse(self.app.metric)
        self.assertTrue(self.app.warning)

    def test_no_data_and_activity_error_are_independent(self):
        with patch.object(finops, "load_usage", return_value=pd.DataFrame(columns=COLUMNS)), patch.object(finops, "load_sql_activity", side_effect=finops.MonitoringUnavailable("Historique inaccessible")):
            self.app.run().button(key="finops_refresh").click().run()
            self.app.button(key="finops_load_activity").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual([m.value for m in self.app.metric], ["Non disponible"] * 3)
        self.assertTrue(self.app.error)

    def test_execution_seconds_do_not_create_a_compute_cost(self):
        activity = pd.DataFrame([dict(nombre_requetes=50, secondes_execution=Decimal("300"))])
        with patch.object(finops, "load_usage", return_value=usage_frame()), patch.object(finops, "load_sql_activity", return_value=activity):
            self.app.run().button(key="finops_refresh").click().run()
            self.app.button(key="finops_load_activity").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual([m.value for m in self.app.metric], ["12,00 €", "Non disponible", "12,00 €", "50", "300,00 s"])

    def test_identity_change_clears_snapshot(self):
        with patch.object(finops, "load_usage", return_value=usage_frame()):
            self.app.run().button(key="finops_refresh").click().run()
        with patch.object(finops, "authorize_monitoring", return_value=dict(ADMIN, email="other@example.test")):
            self.app.run()
        self.assertFalse(self.app.metric)

    def test_missing_configuration_and_non_admin_route(self):
        self.app.session_state["finops_settings"] = dict(SETTINGS, app_id="")
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.metric)
        self.app.session_state["current_user"] = dict(ADMIN, profil="agent")
        self.app.run()
        self.assertTrue(self.app.error)
        self.assertFalse(self.app.text_input)


if __name__ == "__main__":
    unittest.main()
