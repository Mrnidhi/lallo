"""Synthetic checks only. No Databricks connection or company data is used.

Run with: python -m unittest discover -s grain-review -p 'test_*.py' -v
Requires duckdb and sqlglot in the local test environment, not in Databricks.
"""
import ast
from decimal import Decimal
from pathlib import Path
import re
import unittest

import duckdb
import sqlglot

SOURCE_PATH = Path(__file__).with_name("CSM_CSAL_GRAIN_REVIEW.py")
TREE = ast.parse(SOURCE_PATH.read_text())
NAMESPACE = {}
HELPERS = ast.Module(body=[node for node in TREE.body if isinstance(node, ast.FunctionDef)
                          and node.name in {"ident", "literal", "build_metric_query", "build_exception_queries"}], type_ignores=[])
exec(compile(HELPERS, str(SOURCE_PATH), "exec"), NAMESPACE)
query_builder = NAMESPACE["build_metric_query"]

EXCEPTION_CONFIG = {
    node.targets[0].id: ast.literal_eval(node.value)
    for node in TREE.body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    and node.targets[0].id in {"EXCEPTION_KEYS", "MONTHLY_AMOUNTS", "MQC_AMOUNTS", "CONTEXT_COLUMNS"}
}


class ExceptionReviewTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()
        self.columns = list(dict.fromkeys(sum(EXCEPTION_CONFIG.values(), [])))
        text_columns = set(EXCEPTION_CONFIG["EXCEPTION_KEYS"] + ["mqc_status", "swap_tier"])
        flag_columns = {"is_volume_without_csal", "is_swap_donor", "is_swap_receiver"}
        self.defaults = {c: "sample" if c in text_columns else False if c in flag_columns else 0
                         for c in self.columns}
        self.defaults.update(category="Regular CSAL", mqc_status="On Track", swap_tier="Primary")
        definition = ", ".join(f'"{c}" ' + ("VARCHAR" if c in text_columns else "BOOLEAN" if c in flag_columns else "BIGINT")
                               for c in self.columns)
        self.db.execute(f"CREATE TABLE fixture ({definition})")
        self.queries = NAMESPACE["build_exception_queries"](
            "SELECT * FROM fixture", EXCEPTION_CONFIG["EXCEPTION_KEYS"],
            EXCEPTION_CONFIG["MONTHLY_AMOUNTS"], EXCEPTION_CONFIG["MQC_AMOUNTS"])

    def tearDown(self):
        self.db.close()

    def run_queries(self, changes):
        rows = [{**self.defaults, **change} for change in changes]
        self.db.executemany("INSERT INTO fixture VALUES (" + ",".join("?" for _ in self.columns) + ")",
                            [[r[c] for c in self.columns] for r in rows])
        outputs = []
        for query in self.queries.values():
            sql = sqlglot.transpile(query, read="databricks", write="duckdb")[0]
            result = self.db.execute(sql)
            outputs.append([dict(zip([c[0] for c in result.description], r)) for r in result.fetchall()])
        return outputs

    def test_complete_population_is_retained_without_invented_exceptions(self):
        overlap, context, swap = self.run_queries([{}])
        self.assertEqual(overlap[0]["missing_grouping_columns"], "NONE")
        self.assertEqual(overlap[0]["monthly_amounts_null"], 0)
        self.assertEqual(context, [])
        self.assertEqual(swap[0]["source_rows"], 1)

    def test_overlapping_nulls_count_one_physical_row(self):
        nulls = {c: None for c in EXCEPTION_CONFIG["MONTHLY_AMOUNTS"] + EXCEPTION_CONFIG["MQC_AMOUNTS"]}
        overlap, context, _ = self.run_queries([{**nulls, "sales_rep": None, "agreement": None, "booked_teu": None}])
        self.assertEqual(overlap[0]["missing_grouping_columns"], "sales_rep, agreement")
        self.assertEqual(overlap[0]["monthly_amounts_null"], 6)
        self.assertEqual(overlap[0]["mqc_amounts_null"], 3)
        self.assertTrue(overlap[0]["booked_teu_null"])
        self.assertEqual(overlap[0]["source_rows"], 1)
        self.assertEqual(context[0]["source_rows"], 1)

    def test_disjoint_and_shared_missing_populations_are_separate(self):
        overlap, context, _ = self.run_queries([
            {"sales_rep": None}, {"sc_mqc": None}, {"sales_rep": None, "sc_mqc": None}])
        self.assertEqual(len(overlap), 3)
        self.assertEqual(sum(r["source_rows"] for r in overlap), 3)
        self.assertEqual(sum(r["source_rows"] for r in context), 3)

    def test_partial_missing_amounts_and_existing_status_are_preserved(self):
        overlap, context, _ = self.run_queries([{"monthly_booked_teu": None, "ctd_vol": None,
                                                "sc_mqc": None, "mqc_status": "At Risk"}])
        self.assertEqual(overlap[0]["monthly_amounts_null"], 1)
        self.assertEqual(overlap[0]["mqc_amounts_null"], 2)
        self.assertEqual(context[0]["mqc_status"], "At Risk")

    def test_null_blank_and_populated_tiers_are_not_merged(self):
        _, _, swap = self.run_queries([{"swap_tier": None}, {"swap_tier": "  "}, {}])
        self.assertEqual({r["swap_tier_state"] for r in swap}, {"NULL", "BLANK", "POPULATED"})
        self.assertEqual(sum(r["source_rows"] for r in swap), 3)

    def test_empty_tier_alone_is_not_a_missing_amount_or_identity(self):
        overlap, context, swap = self.run_queries([{"swap_tier": None}, {"swap_tier": None}])
        self.assertEqual(context, [])
        self.assertEqual(overlap[0]["source_rows"], 2)
        self.assertEqual(swap[0]["source_rows"], 2)

    def test_swap_null_zero_negative_and_flags_remain_distinct(self):
        _, _, swap = self.run_queries([{"is_swap_donor": None, "swappable_teu": None},
                                       {"total_donor_teu_available": -9}, {}])
        self.assertEqual(sum(r["swappable_null_rows"] for r in swap), 1)
        self.assertEqual(sum(r["donor_available_nonzero_rows"] for r in swap), 1)
        self.assertTrue(any(r["is_swap_donor"] is None for r in swap))

    def test_blank_key_and_null_category_are_visible_without_customer_exports(self):
        overlap, context, _ = self.run_queries([{"agreement": " ", "category": None,
                                               "customer": "Synthetic private label"}])
        self.assertEqual(overlap[0]["missing_grouping_columns"], "agreement, category")
        self.assertIsNone(context[0]["category"])
        self.assertNotIn("Synthetic private label", str(overlap) + str(context))

    def test_all_queries_keep_the_supplied_version_and_month(self):
        source = "SELECT * FROM example VERSION AS OF 90 WHERE month = 'August 2026'"
        queries = NAMESPACE["build_exception_queries"](source, EXCEPTION_CONFIG["EXCEPTION_KEYS"],
                    EXCEPTION_CONFIG["MONTHLY_AMOUNTS"], EXCEPTION_CONFIG["MQC_AMOUNTS"])
        for query in queries.values():
            self.assertEqual(query.count(source), 1)
            self.assertNotIn("CURRENT_DATE", query.upper())


class SqlCountFunctions:
    """SQL equivalent of the three calls in the count helper, not a Spark runtime."""
    @staticmethod
    def lit(value):
        return str(value)

    @staticmethod
    def when(condition, value):
        return f"CASE WHEN {condition} THEN {value} END"

    @staticmethod
    def count(value):
        return f"COUNT({value})"


class ColumnQualityTests(unittest.TestCase):
    def setUp(self):
        self.db = duckdb.connect()
        helper = ast.Module(body=[node for node in TREE.body if isinstance(node, ast.FunctionDef)
                                  and node.name == "count_matching_rows"], type_ignores=[])
        namespace = {"F": SqlCountFunctions}
        exec(compile(helper, str(SOURCE_PATH), "exec"), namespace)
        self.count_matches = namespace["count_matching_rows"]

    def tearDown(self):
        self.db.close()

    def profile(self, values, dtype, predicates):
        self.db.execute(f"CREATE TABLE quality_fixture (value {dtype})")
        if values:
            self.db.executemany("INSERT INTO quality_fixture VALUES (?)", [(v,) for v in values])
        expressions = ", ".join(self.count_matches(p) for p in predicates)
        query = sqlglot.transpile(f"SELECT {expressions} FROM quality_fixture",
                                 read="databricks", write="duckdb")[0]
        # Use int(), as the notebook does, to catch the original NoneType failure.
        return tuple(int(n) for n in self.db.execute(query).fetchone())

    def test_all_null_string_counts_nulls_without_int_none(self):
        self.assertEqual(self.profile([None, None], "VARCHAR",
                                      ["value IS NULL", "TRIM(value) = ''", "FALSE"]), (2, 0, 0))
        original = self.db.execute("SELECT SUM(CAST(TRIM(value) = '' AS BIGINT)) FROM quality_fixture").fetchone()[0]
        self.assertIsNone(original)  # The old expression reproduces the reported failure.

    def test_null_blank_and_populated_strings_are_separate(self):
        self.assertEqual(self.profile([None, "", "   ", "A", " A "], "VARCHAR",
                                      ["value IS NULL", "TRIM(value) = ''", "FALSE"]), (1, 2, 0))

    def test_all_null_float_does_not_make_invalid_count_null(self):
        self.assertEqual(self.profile([None, None], "DOUBLE",
                                      ["value IS NULL", "FALSE", "isnan(value) OR abs(value) = CAST('Infinity' AS DOUBLE)"]),
                         (2, 0, 0))

    def test_non_finite_numbers_are_counted_separately_from_nulls(self):
        self.assertEqual(self.profile([None, 0.0, -1.0, float("nan"), float("inf"), -float("inf")], "DOUBLE",
                                      ["value IS NULL", "FALSE", "isnan(value) OR abs(value) = CAST('Infinity' AS DOUBLE)"]),
                         (1, 0, 3))

    def test_zero_and_negative_values_are_not_missing(self):
        self.assertEqual(self.profile([None, 0, -2, 5], "BIGINT",
                                      ["value IS NULL", "FALSE", "FALSE"]), (1, 0, 0))

    def test_no_rows_has_zero_counts_without_removing_source_guard(self):
        self.assertEqual(self.profile([], "VARCHAR",
                                      ["value IS NULL", "TRIM(value) = ''", "FALSE"]), (0, 0, 0))
        self.assertIn("if SOURCE_ROWS == 0:", SOURCE_PATH.read_text())

    def test_all_three_quality_counts_use_the_helper(self):
        loop = next(node for node in TREE.body if isinstance(node, ast.For)
                    and ast.unparse(node.target) == "(position, (name, dtype))")
        calls = [node for node in ast.walk(loop) if isinstance(node, ast.Call)]
        self.assertEqual(sum(isinstance(n.func, ast.Name) and n.func.id == "count_matching_rows"
                             for n in calls), 3)
        self.assertFalse(any(isinstance(n.func, ast.Attribute) and n.func.attr == "sum" for n in calls))


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

    def test_all_nine_cells_are_valid_python(self):
        cells = SOURCE_PATH.read_text().split("# COMMAND ----------")
        self.assertEqual(len(cells), 9)
        for index, cell in enumerate(cells, 1):
            compile(cell, f"cell_{index}", "exec")

    def test_copy_guide_matches_all_nine_source_cells(self):
        source_cells = SOURCE_PATH.read_text().split("# COMMAND ----------")
        copied_cells = re.findall(r"```python\n(.*?)\n```", SOURCE_PATH.with_name("COPY_CELLS.md").read_text(), re.S)
        self.assertEqual(len(copied_cells), 9)
        self.assertEqual([c.strip() for c in source_cells], [c.strip() for c in copied_cells])

    def test_no_company_connections_or_source_writes(self):
        source = SOURCE_PATH.read_text()
        for forbidden in (".saveAsTable(", ".write.", "databricks_openai", "WorkspaceClient(", "requests."):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("AS correct_grain_total", source)
        self.assertNotIn("ROUND(SUM", source)


if __name__ == "__main__":
    unittest.main()
