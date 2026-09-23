"""Synthetic SQL checks; run with Python after installing sqlglot and duckdb.

The Databricks query is parsed and translated to DuckDB for small local fixtures.
This verifies data logic, not a live Databricks execution or source semantics.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

import duckdb
import sqlglot


SOURCE = Path(__file__).resolve().parents[1] / "notebooks/customer-booking-patterns/01_booking_timing.py"


def load_sql_builder():
    tree = ast.parse(SOURCE.read_text())
    module = ast.Module(body=[
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"sql_text", "booking_timing_sql"}
    ], type_ignores=[])
    namespace = {}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["booking_timing_sql"]


class BookingTimingSQL(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("SET TimeZone='UTC'")
        self.con.execute("ATTACH ':memory:' AS datasources")
        self.con.execute("CREATE SCHEMA datasources.csal")
        self.con.execute("""CREATE TABLE datasources.csal.csal_booking_detail (
            shipment_num VARCHAR, ccp_cus_nme VARCHAR, corp_svc_cde VARCHAR,
            corp_vsl_cde VARCHAR, corp_voy_num VARCHAR, corp_voy_dir VARCHAR,
            f_load_svc_cde VARCHAR, f_load_vsl_cde VARCHAR, f_load_voy_num VARCHAR,
            f_load_dir VARCHAR, fpol_port_cde VARCHAR, lpol_port_cde VARCHAR,
            shipment_status VARCHAR, lpol_etd_iodt_utc VARCHAR,
            rec_cre_dt_utc TIMESTAMPTZ, rec_upd_dt_utc TIMESTAMPTZ)""")
        self.con.execute("""CREATE TABLE datasources.csal.csal_shipment (
            shipment_number VARCHAR, rec_cre_dt_utc TIMESTAMPTZ)""")
        self.con.execute("""CREATE TABLE datasources.csal.csal_voy_stop_dtl (
            id BIGINT, msg_business_key VARCHAR, port_code VARCHAR,
            use_dep_svvd BOOLEAN, dep_svvd VARCHAR, arr_svvd VARCHAR,
            tcr_cutoff_date VARCHAR, voy_dep_dt_utc VARCHAR,
            is_load_allowed BOOLEAN, is_omitted BOOLEAN,
            is_tentative_schedule BOOLEAN, is_vms BOOLEAN,
            is_phase_out BOOLEAN, private_call BOOLEAN,
            rec_cre_dt_utc TIMESTAMPTZ, rec_upd_dt_utc TIMESTAMPTZ)""")
        self.cutoff = datetime(2026, 8, 31, tzinfo=timezone.utc)
        self.updated = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self.build = load_sql_builder()

    def tearDown(self):
        self.con.close()

    def insert(self, table, values):
        placeholders = ",".join("?" for _ in values)
        self.con.execute(f"INSERT INTO datasources.csal.{table} VALUES ({placeholders})", values)

    def detail(self, num, service="S1", voyage="001", customer="Customer A",
               port="AAA", first_port="AAA", updated=None,
               departure="20260902080000.000"):
        self.insert("csal_booking_detail", [str(num), customer, service, "VES", voyage,
            "North", service, "VES", voyage, "North", first_port, port,
            "Confirmed", departure, self.cutoff - timedelta(days=5),
            updated or self.updated])

    def shipment(self, num, booked_at):
        self.insert("csal_shipment", [str(num), booked_at])

    def stop(self, num=1, service="S1", voyage="001", cutoff=None,
             key=None, departure="2026-09-02T08:00:00Z", flags=True,
             updated=None):
        svvd = f"{service}-VES-{voyage} N"
        self.insert("csal_voy_stop_dtl", [num, key or f"{svvd}|AAA|1", "AAA",
            True, svvd, svvd, (cutoff or self.cutoff).isoformat(), departure,
            flags, not flags if flags is not None else None, False, False,
            False, False, self.cutoff - timedelta(days=10), updated or self.updated])

    def results(self, services=None, as_of="2026-09-23T00:00:00Z"):
        query = self.build(2026, 56, 14, as_of, services)
        translated = sqlglot.parse_one(query, read="databricks").sql(dialect="duckdb")
        cursor = self.con.execute(translated)
        names = [column[0] for column in cursor.description]
        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        self.assertEqual(len(rows), len({r["shipment_num"] for r in rows}))
        return {r["shipment_num"]: r for r in rows}

    def test_exact_window_edges_and_year_scope(self):
        self.stop()
        offsets = {1: -56 * 86400, 2: -56 * 86400 - .000001,
                   3: -.000001, 4: 0, 5: 14 * 86400 - .000001,
                   6: 14 * 86400}
        for num, seconds in offsets.items():
            self.detail(num)
            self.shipment(num, self.cutoff + timedelta(seconds=seconds))
        self.detail(7)
        self.shipment(7, datetime(2025, 12, 31, tzinfo=timezone.utc))
        self.detail(8)
        self.shipment(8, datetime(2027, 1, 1, tzinfo=timezone.utc))
        rows = self.results()
        self.assertEqual(set(rows), {str(x) for x in range(1, 7)})
        self.assertEqual([rows[str(x)]["day_from_cutoff"] for x in (1, 3, 4, 5)],
                         [-56, -1, 0, 13])
        self.assertTrue(all(rows[str(x)]["coverage_status"] == "Included" for x in (1, 3, 4, 5)))
        self.assertEqual(rows["2"]["coverage_status"], "Booked earlier than comparison window")
        self.assertEqual(rows["6"]["coverage_status"], "Booked later than comparison window")

    def test_revisions_duplicates_names_and_services(self):
        self.stop()
        self.stop(2, service="S2")
        self.detail(1, customer="  Customer\t A  ")
        self.detail(1, customer="  Customer\t A  ")
        self.shipment(1, self.cutoff)
        self.shipment(1, self.cutoff)
        self.detail(2, service="S1", updated=self.updated - timedelta(days=1))
        self.detail(2, service="S2")
        self.shipment(2, self.cutoff)
        self.detail(3, customer="First Name")
        self.detail(3, customer="Other Name")
        self.shipment(3, self.cutoff)
        self.detail(4, customer=" \t ")
        self.shipment(4, self.cutoff)
        rows = self.results()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows["1"]["customer_key"], "CUSTOMER A")
        self.assertEqual(rows["1"]["coverage_status"], "Included")
        self.assertEqual(rows["2"]["service"], "S2")
        self.assertNotIn("2", self.results(["S1"]))
        self.assertEqual(rows["3"]["coverage_status"], "Conflicting current customer or route")
        self.assertEqual(rows["4"]["coverage_status"], "Customer name missing")

    def test_missing_and_conflicting_times_stay_unassigned(self):
        self.stop()
        for num in (1, 2, 3):
            self.detail(num)
        self.shipment(2, None)
        self.shipment(3, self.cutoff)
        self.shipment(3, self.cutoff - timedelta(seconds=1))
        rows = self.results()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["coverage_status"] == "Booking time unresolved; year not assigned"
                            for r in rows.values()))

    def test_stop_disambiguation_flags_and_non_utc_session(self):
        self.stop()
        self.stop(2, key="S1-VES-001 N|AAA|2", departure="2026-09-09T08:00:00Z")
        self.detail(1)
        self.shipment(1, self.cutoff)
        self.detail(2, departure="20260910080000.000")
        self.shipment(2, self.cutoff)
        self.detail(3, voyage="002")
        self.shipment(3, self.cutoff)
        self.stop(3, voyage="002", flags=None)
        self.detail(4, voyage="003")
        self.shipment(4, self.cutoff)
        self.detail(5, first_port="BBB")
        self.shipment(5, self.cutoff)
        self.stop(4, voyage="004")
        self.stop(5, voyage="004", departure="2026-09-09T08:00:00Z")
        self.detail(6, voyage="004")
        self.shipment(6, self.cutoff)
        for zone in ("UTC", "America/Los_Angeles"):
            self.con.execute(f"SET TimeZone='{zone}'")
            rows = self.results()
            self.assertEqual(rows["1"]["coverage_status"], "Included")
            self.assertEqual(rows["1"]["day_from_cutoff"], 0)
            self.assertEqual(rows["2"]["coverage_status"], "More than one possible stop or revision")
            self.assertEqual(rows["3"]["coverage_status"], "Omitted or unavailable loading call")
            self.assertEqual(rows["4"]["coverage_status"], "No matching voyage and loading port")
            self.assertEqual(rows["5"]["coverage_status"], "Connecting route; separate leg cutoff needed")
            self.assertEqual(rows["6"]["coverage_status"], "More than one possible stop or revision")

    def test_complete_followup_and_pre_year_window(self):
        early = datetime(2026, 2, 1, tzinfo=timezone.utc)
        future = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.stop(1, voyage="001", cutoff=early)
        self.stop(2, voyage="002", cutoff=future)
        self.detail(1)
        self.shipment(1, early)
        self.detail(2, voyage="002")
        self.shipment(2, future)
        rows = self.results()
        self.assertEqual(rows["1"]["coverage_status"], "Full pre-cutoff window not inside selected year")
        self.assertEqual(rows["2"]["coverage_status"], "Full post-cutoff window not yet observed")
        self.assertEqual(self.results(as_of="2026-10-04T00:00:00Z")["2"]["coverage_status"], "Included")


if __name__ == "__main__":
    unittest.main()
