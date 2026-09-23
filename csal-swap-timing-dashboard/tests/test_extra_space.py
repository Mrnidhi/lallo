"""Synthetic checks for the customer booking and requested-space notebook.

Runs pure helpers only; Spark and company sources are never accessed.
SQL is parsed as Databricks and evaluated on small DuckDB fixtures.
"""
import ast
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import re

import duckdb
import sqlglot
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator


SOURCE = Path(__file__).resolve().parents[1] / "notebooks/csal-customer-bookings-and-extra-space.py"


def load_helpers():
    names = {"sql_text", "clean_customer", "extra_space_sql", "parse_audit_time",
             "classify_event_times", "summarize_extra_space", "plot_booking_and_space"}
    tree = ast.parse(SOURCE.read_text())
    module = ast.Module(body=[node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    namespace = {"datetime": datetime, "timezone": timezone, "ZoneInfo": ZoneInfo,
                 "re": re, "np": np, "pd": pd, "plt": plt, "mdates": mdates,
                 "MaxNLocator": MaxNLocator}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


HELPERS = load_helpers()


class ExtraSpaceSQL(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("SET TimeZone='UTC'")
        self.con.execute("ATTACH ':memory:' AS datasources")
        self.con.execute("CREATE SCHEMA datasources.csal")
        self.con.execute("""CREATE TABLE datasources.csal.csal_change_log (
            csal_id BIGINT, customer VARCHAR, service VARCHAR,
            vessel_voyage VARCHAR, agreement VARCHAR)""")
        self.con.execute("""CREATE TABLE datasources.csal.csal_audit_trail (
            uuid BIGINT, csal_id BIGINT, type VARCHAR, change_field VARCHAR,
            change_from VARCHAR, change_to VARCHAR, user_name VARCHAR, date_time VARCHAR)""")

    def tearDown(self):
        self.con.close()

    def context(self, plan=1, customer="Customer A", service="S1", voyage="VES001", agreement="A1"):
        self.con.execute("INSERT INTO datasources.csal.csal_change_log VALUES (?,?,?,?,?)",
                         [plan, customer, service, voyage, agreement])

    def audit(self, audit_id=1, plan=1, action="grid edit", field="requestedTeu",
              before="2", after="5", user="Editor One", raw="20260601090000.000"):
        self.con.execute("INSERT INTO datasources.csal.csal_audit_trail VALUES (?,?,?,?,?,?,?,?)",
                         [audit_id, plan, action, field, before, after, user, raw])

    def result(self, services=None, customer=None):
        query = HELPERS["extra_space_sql"](2026, services, customer)
        translated = sqlglot.parse_one(query, read="databricks").sql(dialect="duckdb")
        return self.con.execute(translated).fetchdf()

    def test_allowlisted_requested_edits_only_and_initial_not_zero(self):
        self.context()
        self.audit(1)
        self.audit(2, action=" multi edit ", before="5", after="8", raw="20260602090000.000")
        self.audit(3, action="finalize", before="8", after="10")
        self.audit(4, action="submit", before="8", after="10")
        self.audit(5, field="adjustedTeu")
        self.audit(6, user="System")
        self.audit(7, user=None)
        self.audit(8, before=None)
        self.audit(9, before="n/a")
        self.audit(10, before="-1")
        self.audit(11, before="5", after="2")
        self.audit(12, before="5", after="5")
        self.audit(13, after=None)
        self.audit(14, raw="20250601090000.000")
        result = self.result()
        self.assertNotIn("5", set(result.audit_id))
        self.assertNotIn("14", set(result.audit_id))
        accepted = result[result.evidence_status == "Positive requested-space edit"]
        self.assertEqual(set(accepted.audit_id), {"1", "2"})
        self.assertEqual(accepted.extra_teu.tolist(), [3, 3])
        statuses = result.set_index("audit_id").evidence_status
        self.assertEqual(statuses["8"], "Initial value; not an extra-space increase")
        self.assertEqual(statuses["10"], "Negative quantity")
        self.assertEqual(statuses["13"], "Non-numeric or missing quantity")

    def test_dedup_replayed_rows_conflicting_ids_and_repeated_edit_ids(self):
        self.context()
        self.audit(1)
        self.audit(1)
        self.audit(2, raw="20260602090000.000")
        self.audit(2, after="6", raw="20260602090000.000")
        self.audit(3, raw="20260603090000.000")
        self.audit(4, raw="20260603090000.000")
        self.audit(None, raw="20260604090000.000")
        self.audit(5, raw="20260605090000.000")
        self.audit(5, field="reviewedTeu", raw="20260605090000.000")
        result = self.result()
        self.assertEqual((result.audit_id == "1").sum(), 1)
        accepted = result[result.evidence_status == "Positive requested-space edit"]
        self.assertEqual(accepted.audit_id.tolist(), ["1"])
        self.assertTrue((result[result.audit_id == "2"].evidence_status == "Audit identity unresolved").all())
        self.assertTrue((result[result.audit_id.isin(["3", "4"])].evidence_status ==
                         "Repeated edit under different audit IDs").all())
        self.assertEqual(result[result.audit_id == "5"].evidence_status.iloc[0], "Audit identity unresolved")

    def test_customer_context_stability_and_missing_or_changing_plan(self):
        self.context(1, " Customer\t A ", "s1-n")
        self.context(1, "customer A", "S1")
        self.context(2, "Customer B")
        self.context(2, "Customer C")
        self.context(3, "Customer A", "S1")
        self.context(3, "Customer A", "S2")
        self.context(4, None)
        self.context(5, "Customer D", voyage="VES001", agreement="A1")
        self.context(5, "Customer D", voyage="VES002", agreement="A2")
        for number in range(1, 7):
            self.audit(number, plan=number)
        result = self.result().set_index("plan_id")
        self.assertEqual(result.loc["1", "customer_key"], "CUSTOMER A")
        self.assertEqual(result.loc["1", "service"], "S1")
        self.assertEqual(result.loc["1", "evidence_status"], "Positive requested-space edit")
        for number in ("2", "3"):
            self.assertEqual(result.loc[number, "evidence_status"],
                             "Customer or service varies in available plan history")
        self.assertEqual(result.loc["4", "evidence_status"], "Plan customer or service missing")
        self.assertTrue(pd.isna(result.loc["5", "short_voyage"]))
        self.assertTrue(pd.isna(result.loc["5", "agreement"]))
        self.assertEqual(result.loc["6", "evidence_status"], "No plan customer history available")

    def test_scope_filters_preserve_unresolved_context(self):
        self.context(1, "O'Brien Shipping", "S1")
        self.context(2, "Another Customer", "S2")
        self.context(3, "Other", "S2")
        self.context(3, "Changed", "S3")
        for number in range(1, 5):
            self.audit(number, plan=number)
        result = self.result(["s1"], " O'Brien   Shipping ")
        self.assertEqual(set(result.plan_id), {"1", "3", "4"})
        accepted = result[result.evidence_status == "Positive requested-space edit"]
        self.assertEqual(accepted.plan_id.tolist(), ["1"])
        self.assertEqual(len(self.result()), 4)
        with self.assertRaises(ValueError):
            HELPERS["extra_space_sql"](2026, "S1")
        with self.assertRaises(ValueError):
            HELPERS["extra_space_sql"](2026, [])

    def test_empty_sources_and_cross_year_id_conflict(self):
        self.assertTrue(self.result().empty)
        self.context()
        self.audit(1)
        self.audit(1, raw="20250601090000.000")
        result = self.result()
        self.assertEqual(len(result), 1)
        self.assertEqual(result.evidence_status.iloc[0], "Audit identity unresolved")


class ExtraSpaceHelpers(unittest.TestCase):
    def events(self):
        return pd.DataFrame([
            {"audit_id": str(i), "plan_id": "P1", "service": "S1", "customer_key": "CUSTOMER A",
             "customer": "Customer A", "evidence_status": "Positive requested-space edit",
             "previous_requested_teu": old, "requested_total_teu": new, "extra_teu": new - old,
             "raw_event_time": raw}
            for i, (old, new, raw) in enumerate([
                (1, 3, "20260601090000.000"), (3, 6, "20260601100000.000"),
                (6, 16, "20260602090000.000")], start=1)
        ])

    def test_unknown_zone_preserves_clock_and_offsets_override_config(self):
        parser = HELPERS["parse_audit_time"]
        wall, utc, status = parser("20260601093022.123")
        self.assertEqual(wall, datetime(2026, 6, 1, 9, 30, 22, 123000))
        self.assertIsNone(utc)
        self.assertEqual(status, "Timezone unconfirmed; recorded clock only")
        _, utc, status = parser("20260601093022.123+0800", "America/Los_Angeles")
        self.assertEqual(utc, datetime(2026, 6, 1, 1, 30, 22, 123000, tzinfo=timezone.utc))
        self.assertEqual(status, "Explicit timezone offset")
        self.assertEqual(parser("2026-06-01T09:30:22Z")[1].hour, 9)

    def test_confirmed_zone_dst_and_invalid_timestamps(self):
        parser = HELPERS["parse_audit_time"]
        _, utc, status = parser("20260601090000.000", "America/Los_Angeles")
        self.assertEqual(utc.hour, 16)
        self.assertEqual(status, "Configured audit timezone")
        for raw in ("20260308023000.000", "20261101013000.000"):
            self.assertEqual(parser(raw, "America/Los_Angeles")[2], "Ambiguous or nonexistent local time")
            self.assertIsNone(parser(raw, "America/Los_Angeles")[1])
        for raw in (None, "", "20260601", "2026-06-01", "20260230090000.000", "garbage"):
            self.assertEqual(parser(raw), (None, None, "Timestamp unreadable"))

    def test_future_and_unreadable_timestamps_not_accepted(self):
        events = self.events()
        events.loc[0, "raw_event_time"] = "20260701000000Z"
        events.loc[1, "raw_event_time"] = "2026 invalid"
        result = HELPERS["classify_event_times"](events, as_of=datetime(2026, 6, 15, tzinfo=timezone.utc))
        self.assertEqual(result.evidence_status.tolist(), ["Positive edit; timestamp after read time",
            "Positive edit; timestamp unreadable", "Positive requested-space edit"])
        self.assertTrue(result.event_time_utc.iloc[0].endswith("+00:00"))
        self.assertTrue(pd.isna(result.event_time_utc.iloc[2]))

    def test_min_median_max_are_event_deltas_not_daily_totals(self):
        events = self.events()
        excluded = events.iloc[[0]].copy()
        excluded["extra_teu"] = 999
        excluded["evidence_status"] = "System or unidentified editor"
        result = HELPERS["summarize_extra_space"](pd.concat([events, excluded], ignore_index=True))
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual((row.min_extra_teu, row.median_extra_teu, row.max_extra_teu), (2, 3, 10))
        self.assertEqual((row.min_requested_total_teu, row.median_requested_total_teu, row.max_requested_total_teu),
                         (3, 6, 16))
        self.assertEqual(row.recorded_increases, 3)
        self.assertEqual(row.plans, 1)

    def test_empty_events_preserve_schema(self):
        events = HELPERS["classify_event_times"](self.events().iloc[:0])
        self.assertTrue(events.empty)
        self.assertIn("recorded_clock", events)
        self.assertIn("event_time_utc", events)
        summary = HELPERS["summarize_extra_space"](events)
        self.assertTrue(summary.empty)
        self.assertIn("min_extra_teu", summary)
        self.assertIn("median_requested_total_teu", summary)

    def test_chart_renders_two_panels_without_invented_cutoff_alignment(self):
        events = HELPERS["classify_event_times"](self.events())
        daily = pd.DataFrame({"day_from_cutoff": [-4, -1, 0, 2], "bookings": [5, 3, 2, 1]})
        images = []
        figures = []
        with tempfile.TemporaryDirectory() as folder:
            def save_chart():
                fig = plt.gcf()
                figures.append(fig)
                path = Path(folder) / f"chart-{len(images)}.png"
                fig.savefig(path, dpi=100)
                images.append(path)
            with patch.object(plt, "show", side_effect=save_chart):
                HELPERS["plot_booking_and_space"](daily, events, "Customer A", "S1")
                HELPERS["plot_booking_and_space"](daily.iloc[:0], events.iloc[:0], "Customer B", "S2")
            self.assertTrue(all(path.stat().st_size > 10000 for path in images))
            self.assertTrue(all(len(fig.axes) == 2 for fig in figures))
            self.assertEqual(figures[0].axes[0].get_ylabel(), "Bookings per day")
            self.assertEqual(figures[0].axes[1].get_ylabel(), "Added TEU per edit")
            self.assertIn("timezone unconfirmed", figures[0].axes[1].get_xlabel())
            self.assertIn("min 2 · median 3 · max 10", figures[0].axes[1].texts[0].get_text())
            self.assertIn("no request-to-cutoff timing is inferred", figures[0].texts[-1].get_text())


if __name__ == "__main__":
    unittest.main()
