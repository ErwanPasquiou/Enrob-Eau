from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from services import cost_monitoring_service as finops
from services import finops_resource_service as resources
from services.cost_monitoring_demo import demo_usage, reference_data


ROOT = Path(__file__).resolve().parents[1]
ADMIN = dict(email="admin@example.test", prenom="Test", nom="Admin", actif=True, profil="administrateur")
SERVER, COMPUTE = resources.DEMO_DEFAULTS


def frame(values=("12",), unit="DBU", missing=0):
    return pd.DataFrame([[date(2026, 10, 1), "Détail", unit, value, 1, missing, "Test"] for value in values], columns=finops.COLUMNS)


class CalculationTests(unittest.TestCase):
    def test_server_dbu_and_compute_seconds_use_distinct_prices(self):
        server = finops.summarize_resource(finops.price_usage(frame(), SERVER))
        compute = finops.summarize_resource(finops.price_usage(frame(["300"], "s"), COMPUTE))
        self.assertEqual(server["cost"], Decimal("12"))
        self.assertEqual(compute["cost"], Decimal("0.075"))
        self.assertEqual(finops.price_usage(frame(["3600"], "s"), COMPUTE).cout_eur[0], Decimal("0.9"))

    def test_corrections_preserve_negative_net_and_no_intermediate_rounding(self):
        priced = finops.price_usage(frame(["12", "-12", "10.1"]), dict(SERVER, rate="0.75"))
        self.assertEqual(finops.summarize_resource(priced)["cost"], Decimal("7.575"))
        self.assertEqual(finops.price_usage(frame(["-12"]), SERVER).cout_eur[0], Decimal("-12"))

    def test_missing_or_wrong_units_do_not_become_free_usage(self):
        for data in (frame([], "DBU"), frame([None]), frame(["12"], "s")):
            summary = finops.summarize_resource(finops.price_usage(data, SERVER))
            self.assertIsNone(summary["cost"])
        self.assertTrue(finops.summarize_resource(finops.price_usage(frame(["300"], "s", 2), COMPUTE))["partial"])

    def test_negative_compute_duration_is_rejected(self):
        summary = finops.summarize_resource(finops.price_usage(frame(["-10"], "s"), COMPUTE))
        self.assertIsNone(summary["cost"])
        self.assertTrue(summary["partial"])

    def test_rates_accept_comma_and_zero_but_not_invalid_values(self):
        self.assertEqual(finops.parse_rate("0,90"), Decimal("0.90"))
        self.assertEqual(finops.parse_rate("0"), 0)
        for value in ("", None, "-1", "NaN", "Infinity", "texte"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                finops.parse_rate(value)

    def test_annual_periods_include_leap_day_and_current_year_stops_today(self):
        today = date(2026, 10, 17)
        self.assertEqual(finops.period_dates("year", today), (date(2026, 1, 1), today))
        self.assertEqual(finops.period_dates("previous_year", today), (date(2025, 1, 1), date(2025, 12, 31)))
        start, end = finops.period_dates("two_years_ago", today)
        self.assertEqual((end - start).days + 1, 366)
        self.assertEqual(finops.period_dates("previous_month", date(2024, 3, 1)), (date(2024, 2, 1), date(2024, 2, 29)))

    def test_period_and_identifier_validation(self):
        with self.assertRaises(ValueError):
            finops.validate_period(date(2026, 10, 2), date(2026, 10, 1))
        with self.assertRaises(ValueError):
            finops.validate_period(date(2022, 1, 1), date(2026, 1, 1))
        for values in (dict(SERVER, name=""), dict(SERVER, external_id="' OR 1=1"), dict(SERVER, kind="other")):
            with self.assertRaises(ValueError):
                finops.validate_resource(values)


class ReferenceDatasetTests(unittest.TestCase):
    def test_reference_compute_totals_and_cost(self):
        reference = reference_data()
        self.assertEqual(sum(Decimal(row["seconds"]) for row in reference["compute_totals"]), Decimal("398513.00"))
        self.assertEqual(sum(row["queries"] for row in reference["compute_totals"]), 24534)
        data = demo_usage(COMPUTE, date(2026, 10, 8), date(2026, 10, 14))
        self.assertEqual(data.consommation.sum(), Decimal("398513.00"))
        self.assertEqual(data.nombre_requetes.sum(), 24534)
        self.assertEqual(finops.summarize_resource(finops.price_usage(data, COMPUTE))["cost"], Decimal("99.62825"))
        self.assertTrue(data.origine.str.contains("fictives").all())
        for actor in reference["compute_totals"]:
            subset = data.loc[data.detail == actor["actor"]]
            self.assertEqual(subset.consommation.sum(), Decimal(actor["seconds"]))
            self.assertEqual(subset.nombre_requetes.sum(), actor["queries"])

    def test_every_visible_server_reference_is_preserved(self):
        for day, quantity in reference_data()["server_daily_dbu"]:
            result = demo_usage(SERVER, date.fromisoformat(day), date.fromisoformat(day))
            self.assertEqual(result.consommation[0], Decimal(quantity))
            self.assertEqual(result.origine[0], "Capture serveur")

    def test_historical_and_added_resource_rows_are_explicitly_simulated(self):
        result = demo_usage(SERVER, date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(len(result), 366)
        self.assertTrue(result.origine.eq("Historique simulé").all())
        other = demo_usage(dict(SERVER, external_id="another-demo-server"), date(2026, 10, 14), date(2026, 10, 14))
        self.assertEqual(other.origine[0], "Historique simulé")

    def test_data_is_deterministic_and_contains_no_real_identities(self):
        first = demo_usage(COMPUTE, date(2025, 1, 1), date(2025, 1, 31))
        pd.testing.assert_frame_equal(first, demo_usage(COMPUTE, date(2025, 1, 1), date(2025, 1, 31)))
        text = str(reference_data())
        self.assertNotIn("@", text)
        self.assertNotIn("executed_by_user_id", text)
        self.assertTrue((first.loc[first.consommation > 0, "nombre_requetes"] > 0).all())


class QueryTests(unittest.TestCase):
    def test_server_reads_only_billing_and_keeps_all_record_types(self):
        with patch.object(finops, "authorize_monitoring"), patch.object(finops, "_read", return_value=frame()) as read:
            finops.load_resource_usage(SERVER, date(2026, 1, 1), date(2026, 10, 17), "live")
        query, parameters = read.call_args.args
        self.assertIn("`system`.`billing`.`usage`", query)
        self.assertNotIn("system.query", query)
        self.assertNotIn("record_type", query)
        self.assertNotIn(SERVER["external_id"], query)
        self.assertEqual(parameters, [SERVER["external_id"], date(2026, 1, 1), date(2026, 10, 17)])

    def test_compute_reads_query_seconds_with_utc_boundaries(self):
        with patch.object(finops, "authorize_monitoring"), patch.object(finops, "_read", return_value=frame(["300"], "s")) as read:
            finops.load_resource_usage(COMPUTE, date(2024, 1, 1), date(2024, 12, 31), "live")
        query, parameters = read.call_args.args
        self.assertIn("`system`.`query`.`history`", query)
        self.assertIn("SUM(execution_duration_ms) / 1000.0", query)
        self.assertIn("COUNT(*)", query)
        self.assertNotIn("billing", query)
        self.assertEqual(parameters, [COMPUTE["external_id"], "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"])

    def test_sources_are_validated_before_query(self):
        with patch.object(finops, "authorize_monitoring"), patch.object(finops, "_read") as read:
            with self.assertRaises(ValueError):
                finops.load_resource_usage(SERVER, date(2026, 1, 1), date(2026, 1, 2), "live", "source;DROP")
            read.assert_not_called()

    def test_demo_never_connects_and_real_fallback_is_denied(self):
        with patch.object(finops, "require_admin", return_value=ADMIN), patch.object(finops, "is_local_mode", return_value=True), patch.object(finops, "get_connection") as connection:
            result = finops.load_resource_usage(SERVER, date(2026, 1, 1), date(2026, 1, 2), "demo")
            self.assertEqual(len(result), 2)
            with self.assertRaises(finops.MonitoringUnavailable):
                finops.load_resource_usage(SERVER, date(2026, 1, 1), date(2026, 1, 2), "live")
            connection.assert_not_called()

    def test_non_admin_cannot_read_either_mode(self):
        with patch.object(finops, "require_admin", side_effect=PermissionError("Refusé")), patch.object(finops, "get_connection") as connection:
            for mode in ("demo", "live"):
                with self.assertRaises(PermissionError):
                    finops.load_resource_usage(SERVER, date(2026, 1, 1), date(2026, 1, 2), mode)
            connection.assert_not_called()

    def test_connection_sets_utc_and_preserves_decimal(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.description = [("consommation",)]
        cursor.fetchall.return_value = [(Decimal("1.123456789"),)]
        with patch.object(finops, "get_connection", return_value=connection):
            result = finops._read("SELECT ?", [1])
        self.assertEqual(result.iloc[0, 0], Decimal("1.123456789"))
        self.assertEqual(cursor.execute.call_args_list[0].args, ("SET TIME ZONE 'UTC'",))
        self.assertEqual(cursor.execute.call_args_list[1].args, ("SELECT ?", [1]))

    def test_errors_do_not_return_empty_data_or_expose_connection_details(self):
        with patch.object(finops, "get_connection", side_effect=RuntimeError("sensitive-detail")), self.assertRaises(finops.MonitoringUnavailable) as caught:
            finops._read("SELECT 1", [])
        self.assertNotIn("sensitive-detail", str(caught.exception))


class ResourceFixture(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for patcher in (patch.object(resources, "DATABASE_PATH", Path(temporary.name) / "finops.sqlite3"), patch.object(resources, "require_admin", return_value=ADMIN)):
            patcher.start()
            self.addCleanup(patcher.stop)


class ResourceTests(ResourceFixture):
    def test_add_edit_persist_and_keep_modes_separate(self):
        self.assertEqual(len(resources.list_resources("demo")), 2)
        self.assertEqual(resources.list_resources("live"), [])
        created = resources.save_resource("demo", dict(SERVER, name="Second serveur", external_id="second"))
        row = next(row for row in resources.list_resources("demo") if row["id"] == created)
        resources.save_resource("demo", dict(row, external_id="changed", rate="1,25"), created, row["version"])
        updated = next(row for row in resources.list_resources("demo") if row["id"] == created)
        self.assertEqual(updated["rate"], "1.25")
        self.assertEqual(updated["external_id"], "changed")
        self.assertEqual(updated["version"], 2)
        self.assertEqual(len(resources.list_resources("demo")), 3)
        self.assertEqual(resources.list_resources("live"), [])

    def test_duplicate_and_stale_edits_are_rejected_without_losing_data(self):
        row = resources.list_resources("demo")[0]
        with self.assertRaises(ValueError):
            resources.save_resource("demo", row)
        resources.save_resource("demo", dict(row, rate="2"), row["id"], row["version"])
        with self.assertRaises(ValueError):
            resources.save_resource("demo", dict(row, rate="3"), row["id"], row["version"])
        self.assertEqual(next(r for r in resources.list_resources("demo") if r["id"] == row["id"])["rate"], "2")

    def test_mode_and_type_cannot_be_changed_by_an_edit(self):
        row = resources.list_resources("demo")[0]
        with self.assertRaises(ValueError):
            resources.save_resource("live", row, row["id"], row["version"])
        with self.assertRaises(ValueError):
            resources.save_resource("demo", dict(row, kind="compute" if row["kind"] == "serveur" else "serveur"), row["id"], row["version"])

    def test_settings_require_admin_for_reads_and_writes(self):
        with patch.object(resources, "require_admin", side_effect=PermissionError("Refusé")):
            with self.assertRaises(PermissionError):
                resources.list_resources("demo")
            with self.assertRaises(PermissionError):
                resources.save_resource("demo", SERVER)
        self.assertFalse(resources.DATABASE_PATH.exists())


class MonitoringInterfaceTests(ResourceFixture):
    def setUp(self):
        super().setUp()
        for patcher in (patch.object(finops, "require_admin", return_value=ADMIN), patch.object(finops, "is_local_mode", return_value=False),
                        patch("components.cost_monitoring._setting", side_effect=lambda name, default="": default)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = AppTest.from_file(str(ROOT / "pages/administration.py"))
        self.app.session_state["current_user"] = ADMIN.copy()
        self.app.session_state["admin_section"] = "Consommation et coûts"

    def test_demo_has_metrics_graphs_tables_without_databricks(self):
        with patch.object(finops, "get_connection", side_effect=AssertionError("No Databricks")):
            self.app.run(timeout=30)
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.metric), 3)
        self.assertTrue(any("DÉMONSTRATION" in warning.value for warning in self.app.warning))
        self.assertEqual([tab.label for tab in self.app.tabs], ["Graphiques", "Tableaux"])
        self.assertEqual(len(self.app.dataframe), 3)

    def test_switching_year_changes_actual_rows_and_includes_leap_year(self):
        self.app.run(timeout=30).selectbox(key="finops_v2_period").select("two_years_ago").run(timeout=30)
        self.assertFalse(self.app.exception)
        detail = self.app.dataframe[-1].value
        expected_year = date.today().year - 2
        self.assertTrue(all(day.year == expected_year for day in detail["Jour UTC"]))

    def test_add_popup_persists_a_third_followed_resource(self):
        self.app.run(timeout=30).button(key="finops_add").click().run()
        self.assertFalse(self.app.exception)
        self.app.text_input[0].set_value("Second serveur")
        self.app.text_input[1].set_value("DEMO-SECOND")
        next(b for b in self.app.button if b.label == "Enregistrer").click().run(timeout=30)
        self.assertFalse(self.app.exception)
        self.assertEqual(len(resources.list_resources("demo")), 3)
        self.assertEqual(len(self.app.dataframe[0].value), 3)

    def test_edit_popup_recalculates_rate_and_changes_identifier(self):
        row = resources.list_resources("demo")[0]
        self.app.run(timeout=30)
        previous = self.app.dataframe[0].value.iloc[0]["Coût estimé (€)"]
        self.app.button(key=f"finops_edit_{row['id']}").click().run()
        self.app.text_input[2].set_value("2")
        next(b for b in self.app.button if b.label == "Enregistrer").click().run(timeout=30)
        self.assertFalse(self.app.exception)
        self.assertAlmostEqual(self.app.dataframe[0].value.iloc[0]["Coût estimé (€)"], previous * 2)
        row = resources.list_resources("demo")[0]
        self.app.button(key=f"finops_edit_{row['id']}").click().run()
        self.app.text_input[1].set_value("OTHER-SERVER")
        next(b for b in self.app.button if b.label == "Enregistrer").click().run(timeout=30)
        self.assertFalse(self.app.exception)
        self.assertEqual(resources.list_resources("demo")[0]["external_id"], "OTHER-SERVER")

    def test_live_is_manual_and_never_reuses_demo_snapshot(self):
        resources.list_resources("live", [SERVER, COMPUTE])
        with patch.object(finops, "_read", return_value=frame()) as read:
            self.app.run(timeout=30).radio(key="finops_source").set_value("Databricks").run()
            read.assert_not_called()
            self.assertFalse(self.app.metric)
            self.app.button(key="finops_refresh").click().run(timeout=30)
            self.assertEqual(read.call_count, 2)
            self.app.run()
            self.assertEqual(read.call_count, 2)

    def test_partial_failure_keeps_other_resource_and_marks_partial_total(self):
        resources.list_resources("live", [SERVER, COMPUTE])
        self.app.session_state["finops_source"] = "Databricks"
        with patch.object(finops, "_read", side_effect=[frame(), finops.MonitoringUnavailable("Compute indisponible")]):
            self.app.run().button(key="finops_refresh").click().run(timeout=30)
        self.assertFalse(self.app.exception)
        self.assertEqual([m.value for m in self.app.metric], ["12,00 €", "Non disponible", "12,00 €"])
        self.assertIn("partiel", self.app.metric[2].label)

    def test_failure_after_refresh_does_not_leave_old_amounts(self):
        resources.list_resources("live", [SERVER])
        self.app.session_state["finops_source"] = "Databricks"
        with patch.object(finops, "_read", side_effect=[frame(), finops.MonitoringUnavailable("Indisponible")]):
            self.app.run().button(key="finops_refresh").click().run(timeout=30)
            self.app.button(key="finops_refresh").click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(all(m.value == "Non disponible" for m in self.app.metric))

    def test_non_admin_and_lost_permission_hide_data(self):
        self.app.run(timeout=30)
        with patch.object(finops, "require_admin", side_effect=PermissionError("Droits retirés")):
            self.app.run()
        self.assertFalse(self.app.metric)
        self.assertTrue(self.app.error)
        self.app.session_state["current_user"] = dict(ADMIN, profil="agent")
        self.app.run()
        self.assertFalse(self.app.radio)

    def test_custom_dates_and_empty_selection_are_handled(self):
        self.app.run(timeout=30).selectbox(key="finops_v2_period").select("custom").run()
        self.assertFalse(self.app.exception)
        self.assertEqual(len(self.app.date_input), 2)
        self.app.multiselect[0].set_value([]).run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.metric)

    def test_identity_change_and_period_change_invalidate_real_snapshot(self):
        resources.list_resources("live", [SERVER])
        self.app.session_state["finops_source"] = "Databricks"
        with patch.object(finops, "_read", return_value=frame()):
            self.app.run().button(key="finops_refresh").click().run(timeout=30)
        with patch.object(finops, "require_admin", return_value=dict(ADMIN, email="other@example.test")):
            self.app.run()
        self.assertFalse(self.app.metric)
        with patch.object(finops, "_read", return_value=frame()):
            self.app.button(key="finops_refresh").click().run(timeout=30)
        self.app.selectbox(key="finops_v2_period").select("previous_year").run()
        self.assertFalse(self.app.metric)


if __name__ == "__main__":
    unittest.main()
