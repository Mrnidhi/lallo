"""Synthetic checks only. No Databricks connection or company data is used.

Run with: python -m unittest discover -s grain-review -p 'test_*.py' -v
Requires duckdb and sqlglot in the local test environment, not in Databricks.
"""
import ast
from decimal import Decimal
from pathlib import Path
import unittest

import duckdb
import sqlglot

SOURCE_PATH = Path(__file__).with_name("CSM_CSAL_GRAIN_REVIEW.py")
TREE = ast.parse(SOURCE_PATH.read_text())
NAMESPACE = {}
HELPERS = ast.Module(body=[node for node in TREE.body if isinstance(node, ast.FunctionDef)
                          and node.name in {"ident", "literal", "build_metric_query"}], type_ignores=[])
exec(compile(HELPERS, str(SOURCE_PATH), "exec"), NAMESPACE)
query_builder = NAMESPACE["build_metric_query"]


class GrainReviewTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()

    def tearDown(self):
        self.db.close()

    def review(self, rows, sql_type="DECIMAL(24,6)", keys=None):
        self.db.execute(f"CREATE TABLE fixture (month VARCHAR, customer VARCHAR, category VARCHAR, amount {sql_type})")
        if rows:
            self.db.executemany("INSERT INTO fixture VALUES (?, ?, ?, ?)", rows)
        query = query_builder("SELECT * FROM fixture", keys or ["month", "customer"], "amount", "CANDIDATE")
        # Parse the exact emitted SQL as Databricks SQL, then execute its equivalent locally.
        executable = sqlglot.transpile(query, read="databricks", write="duckdb")[0]
        result = self.db.execute(executable)
        return dict(zip([column[0] for column in result.description], result.fetchone()))

    def test_identical_copies_produce_candidate_not_business_pass(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "A", "y", 10)])
        self.assertEqual(r["raw_non_null_sum"], 20)
        self.assertEqual(r["candidate_grain_total"], 10)
        self.assertEqual(r["raw_minus_candidate"], 10)
        self.assertEqual(r["repeated_groups"], 1)
        self.assertEqual(r["diagnostic_status"], "CONSISTENT_CANDIDATE_NOT_BUSINESS_VALIDATED")
        self.assertEqual(r["business_status"], "PENDING_IDENTITY_GRAIN_AND_ADDITIVITY_VALIDATION")

    def test_distinct_values_block_min_or_max_selection(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "A", "y", 20)])
        self.assertEqual(r["conflicting_groups"], 1)
        self.assertIsNone(r["candidate_grain_total"])
        self.assertIsNone(r["raw_minus_candidate"])
        self.assertIsNone(r["eligible_candidate_subtotal"])
        self.assertEqual(r["excluded_source_rows"], 2)

    def test_null_and_value_are_a_conflict(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "A", "y", None)])
        self.assertEqual(r["conflicting_groups"], 1)
        self.assertEqual(r["null_metric_rows"], 1)
        self.assertIsNone(r["candidate_grain_total"])

    def test_all_null_not_zero_or_success(self):
        r = self.review([("Aug", "A", "x", None), ("Aug", "A", "y", None)])
        self.assertEqual(r["conflicting_groups"], 0)
        self.assertEqual(r["null_metric_rows"], 2)
        self.assertIsNone(r["raw_non_null_sum"])
        self.assertIsNone(r["candidate_grain_total"])
        self.assertEqual(r["diagnostic_status"], "BLOCKED_INCOMPLETE_KEYS_OR_VALUES")

    def test_missing_key_is_counted_not_silently_merged(self):
        r = self.review([("Aug", None, "x", 10), ("Aug", None, "y", 10)])
        self.assertEqual(r["source_rows"], 2)
        self.assertEqual(r["missing_key_rows"], 2)
        self.assertEqual(r["excluded_source_rows"], 2)
        self.assertIsNone(r["candidate_grain_total"])

    def test_blank_key_is_missing(self):
        r = self.review([("Aug", "   ", "x", 10)])
        self.assertEqual(r["missing_key_rows"], 1)
        self.assertIsNone(r["candidate_grain_total"])

    def test_customer_case_and_whitespace_are_preserved(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "a", "x", 10), ("Aug", " A ", "x", 10)])
        self.assertEqual(r["candidate_groups"], 3)
        self.assertEqual(r["candidate_grain_total"], 30)

    def test_equal_amounts_in_different_entities_not_sum_distinct(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "B", "x", 10)])
        self.assertEqual(r["candidate_grain_total"], 20)
        self.assertEqual(r["raw_minus_candidate"], 0)

    def test_no_repetition_is_retained(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "B", "x", 20)])
        self.assertEqual(r["repeated_groups"], 0)
        self.assertEqual(r["raw_minus_candidate"], 0)

    def test_signed_values_can_make_raw_total_lower(self):
        r = self.review([("Aug", "A", "x", -10), ("Aug", "A", "y", -10)])
        self.assertEqual(r["raw_non_null_sum"], -20)
        self.assertEqual(r["candidate_grain_total"], -10)
        self.assertEqual(r["raw_minus_candidate"], -10)

    def test_zero_net_difference_does_not_prove_no_repetition(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "A", "y", 10),
                         ("Aug", "B", "x", -10), ("Aug", "B", "y", -10)])
        self.assertEqual(r["raw_minus_candidate"], 0)
        self.assertEqual(r["repeated_groups"], 2)

    def test_decimal_precision_is_not_rounded_to_integers(self):
        r = self.review([("Aug", "A", "x", Decimal("0.123456")), ("Aug", "A", "y", Decimal("0.123456"))])
        self.assertEqual(r["raw_non_null_sum"], Decimal("0.246912"))
        self.assertEqual(r["candidate_grain_total"], Decimal("0.123456"))

    def test_close_floats_are_not_silently_equal(self):
        r = self.review([("Aug", "A", "x", 1.0), ("Aug", "A", "y", 1.0000000001)], "DOUBLE")
        self.assertEqual(r["conflicting_groups"], 1)
        self.assertIsNone(r["candidate_grain_total"])

    def test_nan_is_blocked(self):
        r = self.review([("Aug", "A", "x", float("nan"))], "DOUBLE")
        self.assertEqual(r["non_finite_rows"], 1)
        self.assertIsNone(r["candidate_grain_total"])
        self.assertIsNone(r["raw_non_null_sum"])

    def test_positive_infinity_is_blocked(self):
        r = self.review([("Aug", "A", "x", float("inf"))], "DOUBLE")
        self.assertEqual(r["non_finite_rows"], 1)
        self.assertIsNone(r["candidate_grain_total"])

    def test_negative_infinity_is_blocked(self):
        r = self.review([("Aug", "A", "x", -float("inf"))], "DOUBLE")
        self.assertEqual(r["non_finite_rows"], 1)
        self.assertIsNone(r["candidate_grain_total"])

    def test_finite_inputs_with_overflowed_sum_are_blocked(self):
        r = self.review([("Aug", "A", "x", 1e308), ("Aug", "A", "y", 1e308)], "DOUBLE")
        self.assertEqual(r["non_finite_rows"], 0)
        self.assertIsNone(r["raw_non_null_sum"])
        self.assertIsNone(r["candidate_grain_total"])
        self.assertEqual(r["diagnostic_status"], "BLOCKED_NON_FINITE_AGGREGATE")

    def test_month_prevents_cross_month_collapse(self):
        r = self.review([("Aug", "A", "x", 10), ("Sep", "A", "x", 10)])
        self.assertEqual(r["candidate_groups"], 2)
        self.assertEqual(r["candidate_grain_total"], 20)

    def test_partial_subtotal_is_not_whole_portfolio(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "A", "y", 10), ("Aug", None, "x", 7)])
        self.assertEqual(r["raw_non_null_sum"], 27)
        self.assertEqual(r["eligible_candidate_subtotal"], 10)
        self.assertEqual(r["excluded_source_rows"], 1)
        self.assertEqual(r["eligible_groups"], 1)
        self.assertIsNone(r["candidate_grain_total"])
        self.assertIsNone(r["raw_minus_candidate"])

    def test_more_keys_can_hide_conflict_without_business_proof(self):
        r = self.review([("Aug", "A", "x", 10), ("Aug", "A", "y", 20)], keys=["month", "customer", "category"])
        self.assertEqual(r["conflicting_groups"], 0)
        self.assertEqual(r["candidate_grain_total"], 30)
        self.assertIn("NOT_BUSINESS_VALIDATED", r["diagnostic_status"])

    def test_empty_source_never_passes(self):
        r = self.review([])
        self.assertEqual(r["diagnostic_status"], "EMPTY_SCOPE")
        self.assertIsNone(r["candidate_grain_total"])
        self.assertIsNone(r["raw_non_null_sum"])

    def test_single_zero_is_a_real_observation(self):
        r = self.review([("Aug", "A", "x", 0)])
        self.assertEqual(r["candidate_grain_total"], 0)
        self.assertEqual(r["raw_minus_candidate"], 0)

    def test_quote_escaping_and_invalid_labels(self):
        self.assertEqual(NAMESPACE["literal"]("O'Brien"), "'O''Brien'")
        self.assertEqual(NAMESPACE["ident"]("odd`column"), "`odd``column`")
        with self.assertRaises(ValueError):
            NAMESPACE["literal"]("unsafe\\label")

    def test_all_eight_cells_are_valid_python(self):
        cells = SOURCE_PATH.read_text().split("# COMMAND ----------")
        self.assertEqual(len(cells), 8)
        for index, cell in enumerate(cells, 1):
            compile(cell, f"cell_{index}", "exec")

    def test_no_company_connections_or_source_writes(self):
        source = SOURCE_PATH.read_text()
        for forbidden in (".saveAsTable(", ".write.", "databricks_openai", "WorkspaceClient(", "requests."):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("AS correct_grain_total", source)
        self.assertNotIn("ROUND(SUM", source)


if __name__ == "__main__":
    unittest.main()
