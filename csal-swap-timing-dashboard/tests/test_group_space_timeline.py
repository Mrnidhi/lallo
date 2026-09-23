"""Synthetic tests for grouped customer booking and requested-space timelines.

Only pure helpers are loaded; these tests do not access Spark or company data.
"""
import ast
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
from pathlib import Path
import re
import unittest
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import duckdb
import sqlglot


SOURCE = (Path(__file__).resolve().parents[1] / "notebooks" /
          "customer-booking-patterns" / "group_space_timeline_core.py")


def load_helpers():
    base_source = SOURCE.parents[1] / "csal-customer-bookings-and-extra-space.py"
    base_tree = ast.parse(base_source.read_text())
    tree = ast.parse(SOURCE.read_text())
    base_helpers = [node for node in base_tree.body if isinstance(node, ast.FunctionDef)
                    and node.name in {"clean_customer", "summarize_extra_space"}]
    module = ast.Module(body=base_helpers + [node for node in tree.body
        if isinstance(node, ast.FunctionDef)], type_ignores=[])
    namespace = {"datetime": datetime, "timezone": timezone, "ZoneInfo": ZoneInfo,
                 "re": re, "np": np, "pd": pd}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def profile(customer, service, bookings, group="G1", order=1):
    return {"customer_key": customer.upper(), "customer": customer,
            "service": service, "bookings": bookings, "timing_group": group,
            "group_order": order, "p25_day": -20.0, "median_day": -14.0,
            "p75_day": -7.0}


class GroupCustomerSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def test_top_customers_rank_across_services_preserving_existing_groups(self):
        profiles = pd.DataFrame([
            profile("Alpha", "S1", 60, "G1", 1),
            profile("Alpha", "S2", 60, "G3", 3),
            profile("Beta", "S1", 100, "G2", 2),
            profile("Gamma", "S2", 90, "G4", 4),
            profile("Limited", "S1", 1000, "Limited history", 99),
        ])
        selected = self.helpers["choose_group_customers"](profiles, top_n=2)
        self.assertEqual(set(selected.customer_key), {"ALPHA", "BETA"})
        self.assertEqual(len(selected), 3)
        self.assertEqual(dict(zip(zip(selected.customer_key, selected.service),
                                  selected.timing_group)),
                         {("ALPHA", "S1"): "G1", ("ALPHA", "S2"): "G3",
                          ("BETA", "S1"): "G2"})

    def test_default_top25_is_distinct_customers_not_rows_or_each_group(self):
        rows = [profile(f"Customer {number:02}", service, 100 - number,
                        f"G{number % 4 + 1}", number % 4 + 1)
                for number in range(30) for service in ("S1", "S2")]
        selected = self.helpers["choose_group_customers"](pd.DataFrame(rows))
        self.assertEqual(selected.customer_key.nunique(), 25)
        self.assertEqual(len(selected), 50)
        self.assertNotIn("CUSTOMER 29", set(selected.customer_key))

    def test_service_filter_and_tie_break_are_deterministic(self):
        profiles = pd.DataFrame([
            profile("Zulu", "S1", 80), profile("Alpha", "S1", 80, "G2", 2),
            profile("Zulu", "S2", 1000), profile("Beta", "S2", 2000),
        ])
        selected = self.helpers["choose_group_customers"](profiles, top_n=1,
                                                         services=["S1"])
        self.assertEqual(selected.customer_key.tolist(), ["ALPHA"])
        self.assertEqual(selected.service.tolist(), ["S1"])
        named = self.helpers["choose_group_customers"](
            profiles, customer_names=["  Zulu  "], services=["S1"])
        self.assertEqual(named.customer_key.tolist(), ["ZULU"])

    def test_limited_history_is_not_relabelled_as_a_group(self):
        profiles = pd.DataFrame([profile("Only", "S1", 2, "Limited history", 99)])
        selected = self.helpers["choose_group_customers"](profiles)
        self.assertTrue(selected.empty)


class RequestTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def setUp(self):
        self.cutoff = pd.Timestamp("2026-07-01T00:00:00Z")
        self.as_of = "2026-09-23T00:00:00Z"
        self.bridge = pd.DataFrame([
            {"plan_id": "P1", "cutoff_us": int(self.cutoff.value // 1000),
             "cutoff_status": "Unique current linked cutoff"},
            {"plan_id": "P2", "cutoff_us": np.nan,
             "cutoff_status": "Multiple current cutoffs"},
        ])

    def events(self, days):
        return pd.DataFrame([
            {"audit_id": str(number), "plan_id": "P1", "extra_teu": number + 1,
             "requested_total_teu": number + 10, "customer_key": "ALPHA", "service": "S1",
             "evidence_status": "Positive requested-space edit",
             "event_time_utc": self.cutoff + pd.Timedelta(days=day)}
            for number, day in enumerate(days)
        ])

    def test_boundaries_and_negative_day_floor(self):
        events = self.events([-56, -56 - 1 / 86400, -1 / 86400, 0,
                              14 - 1 / 86400, 14])
        result = self.helpers["assign_request_timing"](
            events, self.bridge, 56, 14, self.as_of).set_index("audit_id")
        self.assertEqual(len(result), len(events))
        self.assertEqual(set(result[result.timing_status == "Included"].index),
                         {"0", "2", "3", "4"})
        self.assertEqual(int(result.loc["0", "day_from_cutoff"]), -56)
        self.assertEqual(int(result.loc["2", "day_from_cutoff"]), -1)
        self.assertEqual(int(result.loc["3", "day_from_cutoff"]), 0)
        self.assertEqual(int(result.loc["4", "day_from_cutoff"]), 13)

    def test_unknown_time_unresolved_or_missing_cutoff_do_not_become_zero(self):
        events = self.events([-3, -2, -1, 0, 1])
        events.loc[0, "event_time_utc"] = pd.NaT
        events.loc[1, "plan_id"] = "P2"
        events.loc[2, "plan_id"] = "NO_LINK"
        events.loc[3, "evidence_status"] = "System or unidentified editor"
        result = self.helpers["assign_request_timing"](
            events, self.bridge, 56, 14, self.as_of).set_index("audit_id")
        self.assertEqual(set(result[result.timing_status == "Included"].index), {"4"})
        self.assertTrue(result.loc[["0", "1", "2"], "days_from_cutoff"].isna().all())

    def test_duplicate_plan_bridge_is_rejected_before_join_inflation(self):
        duplicate = pd.concat([self.bridge, self.bridge.iloc[[0]]], ignore_index=True)
        with self.assertRaises((ValueError, RuntimeError, pd.errors.MergeError)):
            self.helpers["assign_request_timing"](self.events([-2, -1]), duplicate,
                                                  56, 14, self.as_of)

    def test_naive_recorded_clock_is_not_implicitly_treated_as_utc(self):
        events = self.events([-2])
        events["event_time_utc"] = [datetime(2026, 6, 29, 0, 0)]
        result = self.helpers["assign_request_timing"](events, self.bridge, 56, 14, self.as_of)
        self.assertNotEqual(result.timing_status.iloc[0], "Included")
        self.assertTrue(pd.isna(result.days_from_cutoff.iloc[0]))

    def test_one_plan_many_events_keeps_one_output_row_per_event(self):
        events = self.events([-3, -2, -1])
        result = self.helpers["assign_request_timing"](
            events, self.bridge, 56, 14, self.as_of)
        self.assertEqual(len(result), 3)
        self.assertEqual(result.audit_id.nunique(), 3)
        self.assertEqual(float(result.extra_teu.sum()), 6.0)

    def test_event_after_as_of_is_not_included(self):
        events = self.events([0])
        events.loc[0, "event_time_utc"] = pd.Timestamp("2026-09-24T00:00:00Z")
        bridge = self.bridge.iloc[[0]].copy()
        bridge.loc[:, "cutoff_us"] = int(pd.Timestamp("2026-09-23T00:00:00Z").value // 1000)
        result = self.helpers["assign_request_timing"](events, bridge, 56, 14, self.as_of)
        self.assertNotEqual(result.timing_status.iloc[0], "Included")


class GroupSpaceSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def test_event_level_teu_stats_and_separate_timing_denominator(self):
        selected = pd.DataFrame([profile("Alpha", "S1", 200, "G2", 2),
                                 profile("Beta", "S1", 100, "G3", 3)])
        events = pd.DataFrame([
            {"audit_id": str(number), "plan_id": "P1", "service": "S1",
             "customer_key": "ALPHA", "customer": "Alpha",
             "evidence_status": "Positive requested-space edit",
             "timing_status": timing, "days_from_cutoff": day,
             "extra_teu": amount, "requested_total_teu": total}
            for number, (amount, total, day, timing) in enumerate([
                (2, 5, -10, "Included"), (10, 15, -2, "Included"),
                (3, 18, np.nan, "Audit timezone unconfirmed"),
                (100, 200, 20, "Outside comparison window"),
            ])
        ])
        excluded = events.iloc[[0]].copy()
        excluded["audit_id"] = "system"
        excluded["extra_teu"] = 900
        excluded["evidence_status"] = "System or unidentified editor"
        events = pd.concat([events, excluded], ignore_index=True)
        result = self.helpers["summarize_group_space"](selected, events).set_index("customer_key")
        alpha = result.loc["ALPHA"]
        self.assertEqual(int(alpha.request_count), 4)
        self.assertEqual(int(alpha.request_timed_count), 2)
        self.assertEqual(float(alpha.min_extra_teu), 2)
        self.assertEqual(float(alpha.median_extra_teu), 6.5)
        self.assertEqual(float(alpha.max_extra_teu), 100)
        self.assertEqual(float(alpha.min_requested_total_teu), 5)
        self.assertEqual(float(alpha.median_requested_total_teu), 16.5)
        self.assertEqual(float(alpha.max_requested_total_teu), 200)
        self.assertEqual(float(alpha.request_median_day), -6)
        self.assertEqual(float(alpha.request_p25_day), -8)
        self.assertEqual(float(alpha.request_p75_day), -4)
        self.assertEqual(alpha.timing_group, "G2")
        beta = result.loc["BETA"]
        self.assertEqual(int(beta.request_count), 0)
        self.assertTrue(pd.isna(beta.median_extra_teu))
        self.assertTrue(pd.isna(beta.request_median_day))

    def test_empty_request_source_keeps_booking_customers_and_unknown_quantities(self):
        selected = pd.DataFrame([profile("Alpha", "S1", 200, "G2", 2)])
        events = pd.DataFrame(columns=["audit_id", "plan_id", "service", "customer_key",
            "customer", "evidence_status", "timing_status", "days_from_cutoff",
            "extra_teu", "requested_total_teu"])
        result = self.helpers["summarize_group_space"](selected, events)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.bookings.iloc[0], 200)
        self.assertEqual(result.timing_group.iloc[0], "G2")
        self.assertEqual(result.request_count.iloc[0], 0)
        self.assertEqual(result.request_timed_count.iloc[0], 0)
        self.assertTrue(pd.isna(result.median_extra_teu.iloc[0]))
        self.assertTrue(pd.isna(result.request_median_day.iloc[0]))


class PlanCutoffBridgeSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_helpers()

    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("SET TimeZone='UTC'")
        self.con.execute("ATTACH ':memory:' AS datasources")
        self.con.execute("CREATE SCHEMA datasources.csal")
        self.con.execute("""CREATE TABLE datasources.csal.csal_booking_assoc_evt (
            csal_id VARCHAR, shipment_num VARCHAR, service VARCHAR, match_ind BOOLEAN,
            rec_upd_dt_utc TIMESTAMP, rec_cre_dt_utc TIMESTAMP)""")
        self.con.execute("""CREATE TABLE selected_plans (
            plan_id VARCHAR, service VARCHAR, customer_key VARCHAR, short_voyage VARCHAR)""")
        self.con.execute("""CREATE TABLE booking_reference (
            shipment_num VARCHAR, service VARCHAR, customer_key VARCHAR, svvd VARCHAR,
            loading_port VARCHAR, cutoff_us BIGINT, coverage_status VARCHAR)""")

    def tearDown(self):
        self.con.close()

    def plan(self, plan_id):
        self.con.execute("INSERT INTO selected_plans VALUES (?, 'S1', 'ALPHA', 'VES001')",
                         [plan_id])

    def assoc(self, plan_id, shipment, match=True, updated="2026-06-10 12:00:00"):
        self.con.execute("""INSERT INTO datasources.csal.csal_booking_assoc_evt
                            VALUES (?, ?, 'S1', ?, ?, '2026-06-01 00:00:00')""",
                         [plan_id, shipment, match, updated])

    def booking(self, shipment, port="AAA", cutoff_us=1782864000000000,
                status="Included", customer="ALPHA", voyage="S1-VES-001 N"):
        self.con.execute("INSERT INTO booking_reference VALUES (?, 'S1', ?, ?, ?, ?, ?)",
                         [shipment, customer, voyage, port, cutoff_us, status])

    def result(self):
        query = self.helpers["plan_cutoff_sql"]("selected_plans", "booking_reference")
        translated = sqlglot.parse_one(query, read="databricks").sql(dialect="duckdb")
        return self.con.execute(translated).fetchdf().set_index("plan_id")

    def test_valid_link_and_identical_replay_collapse_to_one_cutoff(self):
        self.plan("P1")
        self.assoc("P1", "B1")
        self.assoc("P1", "B1")
        self.booking("B1")
        row = self.result().loc["P1"]
        self.assertEqual(row.cutoff_status, "Unique current linked cutoff")
        self.assertEqual(int(row.associated_shipments), 1)
        self.assertEqual(int(row.route_cutoffs), 1)
        self.assertEqual(int(row.cutoff_us), 1782864000000000)

    def test_conflicting_tie_and_latest_false_cannot_reuse_older_true(self):
        self.plan("P1")
        self.assoc("P1", "B1", True)
        self.assoc("P1", "B1", False)
        self.booking("B1")
        self.plan("P2")
        self.assoc("P2", "B2", True, "2026-06-09 12:00:00")
        self.assoc("P2", "B2", False, "2026-06-10 12:00:00")
        self.booking("B2")
        result = self.result()
        self.assertTrue(result.cutoff_us.isna().all())
        self.assertTrue((result.cutoff_status == "Association or route context unresolved").all())

    def test_competing_plan_outside_selected_customer_is_still_counted(self):
        self.plan("P1")
        self.assoc("P1", "B1")
        self.assoc("OTHER_PLAN", "B1")
        self.booking("B1")
        row = self.result().loc["P1"]
        self.assertEqual(row.cutoff_status, "Association or route context unresolved")
        self.assertTrue(pd.isna(row.cutoff_us))

    def test_unmatched_second_association_is_not_silently_discarded(self):
        self.plan("P1")
        self.assoc("P1", "B1")
        self.assoc("P1", "B2")
        self.booking("B1")
        row = self.result().loc["P1"]
        self.assertEqual(int(row.associated_shipments), 2)
        self.assertEqual(int(row.unresolved_link_rows), 1)
        self.assertTrue(pd.isna(row.cutoff_us))

    def test_different_ports_do_not_become_one_plan_cutoff_even_if_times_equal(self):
        self.plan("P1")
        self.assoc("P1", "B1")
        self.assoc("P1", "B2")
        self.booking("B1", port="AAA")
        self.booking("B2", port="BBB")
        row = self.result().loc["P1"]
        self.assertEqual(int(row.route_cutoffs), 2)
        self.assertEqual(row.cutoff_status, "Several current routes or cutoffs")
        self.assertTrue(pd.isna(row.cutoff_us))

    def test_bad_context_or_stop_flags_never_uses_nonnull_cutoff(self):
        for number in range(1, 4):
            self.plan(f"P{number}")
            self.assoc(f"P{number}", f"B{number}")
        self.booking("B1", status="Omitted or unavailable loading call")
        self.booking("B2", customer="BETA")
        self.booking("B3", voyage="S1-VES-002 N")
        self.plan("P4")
        result = self.result()
        self.assertTrue(result.cutoff_us.isna().all())
        self.assertEqual(result.loc["P4", "cutoff_status"], "No available shipment association")


class EmptyTableDisplayRegression(unittest.TestCase):
    def setUp(self):
        self.helpers = load_helpers()
        self.display = Mock()
        self.helpers["display"] = self.display

    def test_empty_pandas_reports_message_and_columns_without_spark_inference(self):
        table = pd.DataFrame(columns=["audit_id", "extra_teu"])
        output = io.StringIO()
        with redirect_stdout(output):
            self.helpers["display_result_table"](table, "No request edits for this customer.")
        self.display.assert_not_called()
        self.assertIn("No request edits for this customer.", output.getvalue())
        self.assertIn("audit_id", output.getvalue())
        self.assertIn("extra_teu", output.getvalue())

    def test_nonempty_pandas_is_forwarded_unchanged(self):
        table = pd.DataFrame({"audit_id": ["A1"], "extra_teu": [3.0]})
        self.helpers["display_result_table"](table)
        self.display.assert_called_once()
        self.assertIs(self.display.call_args.args[0], table)

    def test_typed_spark_like_table_does_not_trigger_count_or_collect(self):
        class TypedSparkTable:
            def count(self):
                raise AssertionError("Display guard must not run an extra Spark count.")

            def collect(self):
                raise AssertionError("Display guard must not collect a Spark table.")

            @property
            def empty(self):
                raise AssertionError("A Spark table does not have pandas empty semantics.")

        table = TypedSparkTable()
        self.helpers["display_result_table"](table)
        self.display.assert_called_once()
        self.assertIs(self.display.call_args.args[0], table)

    def test_empty_request_display_sequences_complete_without_empty_schema_error(self):
        def spark_backed_display(table):
            if isinstance(table, pd.DataFrame) and table.empty:
                raise RuntimeError("[CANNOT_INFER_EMPTY_SCHEMA] Can not infer schema from empty dataset.")

        self.display.side_effect = spark_backed_display
        summary = pd.DataFrame({"customer_key": ["ALPHA"], "bookings": [30]})
        daily = pd.DataFrame({"customer_key": ["ALPHA"], "day_from_cutoff": [-3], "bookings": [30]})
        empty_events = pd.DataFrame(columns=["customer_key", "audit_id", "extra_teu"])
        empty_bridge = pd.DataFrame(columns=["plan_id", "cutoff_us", "cutoff_status"])
        other_customer_events = pd.DataFrame({"customer_key": ["BETA"], "audit_id": ["A1"], "extra_teu": [3]})
        other_customer_bridge = pd.DataFrame({"plan_id": ["P1"], "cutoff_us": [1782864000000000],
                                              "cutoff_status": ["Unique current linked cutoff"]})
        for label, events, bridge, expected_native_displays in [
            ("all requests empty", empty_events, empty_bridge, 4),
            ("this customer has no requests", other_customer_events, other_customer_bridge, 6),
        ]:
            with self.subTest(label=label):
                self.display.reset_mock()
                customer_events = events[events.customer_key == "ALPHA"]
                output = io.StringIO()
                with redirect_stdout(output):
                    for table in [summary, events, bridge, daily, summary, customer_events, daily]:
                        self.helpers["display_result_table"](table)
                self.assertEqual(self.display.call_count, expected_native_displays)
                self.assertIn("No matching records.", output.getvalue())

    def test_controller_and_nested_customer_view_route_displays_through_guard(self):
        tree = ast.parse(SOURCE.read_text())
        controller = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and node.name == "run_group_space_timeline")
        calls = [node for node in ast.walk(controller) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertFalse(any(node.func.id == "display" for node in calls),
                         "The controller and nested customer view must use the empty-table guard.")
        self.assertTrue(any(node.func.id == "display_result_table" for node in calls))
        population = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and node.name == "get_group_population")
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "display_result_table" and node.args
                            and isinstance(node.args[0], ast.Name) and node.args[0].id == "diagnostics"
                            for node in ast.walk(population)),
                        "Pandas diagnostics must also use the empty-table guard.")


if __name__ == "__main__":
    unittest.main()
