# CSM/CSAL grain review — copy-ready notebook

Use one Python code block per cell in a personal Databricks notebook. Run the eight cells in order. Read [the interpretation guide](README.md) before using any result in the report.

No extra libraries are required inside Databricks. This file contains the same code as [the importable source notebook](CSM_CSAL_GRAIN_REVIEW.py). The local synthetic test libraries are not notebook dependencies.

Cell 1 selects August 2026 by default and pins the current Delta version once. Set `SOURCE_VERSION = 86` only when deliberately revisiting the historical source. Stop at the first failed cell. No production writes or agent calls occur.

## Cell 1: Choose the source and reporting period

```python
# Databricks notebook source
# DBTITLE 1,1. Choose the source and reporting period
from datetime import datetime, timezone
from hashlib import sha256
from functools import reduce
import json
import re

from pyspark.sql import functions as F
from pyspark.sql import types as T

SOURCE_TABLE = "dev.sales_ai_assistant_gold.csm_csal_summary"
REPORT_MONTH = "August 2026"
SOURCE_VERSION = None  # None pins the current version once. Use 86 for a historical check.

# All comparisons are hypotheses. The notebook never labels an agent answer incorrect.
# It reads the source and metadata; it does not create tables, write files or call agents.
RUN_STARTED_UTC = datetime.now(timezone.utc).isoformat()
metric_queries = {}  # Clear earlier evidence queries when starting a new run.
if not re.fullmatch(r"[A-Za-z_][\w]*\.[A-Za-z_][\w]*\.[A-Za-z_][\w]*", SOURCE_TABLE):
    raise ValueError("Use a three-part catalog.schema.table identifier.")
if SOURCE_VERSION is not None and (type(SOURCE_VERSION) is not int or SOURCE_VERSION < 0):
    raise ValueError("SOURCE_VERSION must be None or a non-negative integer.")
if not isinstance(REPORT_MONTH, str) or not REPORT_MONTH.strip():
    raise ValueError("Set REPORT_MONTH to an exact source month value.")

def ident(name):
    return "`" + name.replace("`", "``") + "`"

def literal(value):
    if "\\" in value or "\n" in value or "\r" in value:
        raise ValueError("SQL labels must not contain backslashes or newlines.")
    return "'" + value.replace("'", "''") + "'"

TABLE_SQL = ".".join(ident(part) for part in SOURCE_TABLE.split("."))
table_detail = spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id", "format").first()
if table_detail["format"].lower() != "delta":
    raise RuntimeError("This review requires a Delta source for version-pinned reads.")
SOURCE_TABLE_ID = table_detail["id"]
history = spark.sql(f"DESCRIBE HISTORY {TABLE_SQL}")
selected_history = history.orderBy(F.desc("version")) if SOURCE_VERSION is None else history.filter(F.col("version") == SOURCE_VERSION)
version_record = selected_history.select("version", "timestamp", "operation").first()
if version_record is None:
    raise RuntimeError("Requested source version was not found. Choose a version explicitly; no fallback was made.")
PINNED_VERSION = int(version_record["version"])
SOURCE_SQL = (
    f"SELECT * FROM {TABLE_SQL} VERSION AS OF {PINNED_VERSION} "
    f"WHERE {ident('month')} = {literal(REPORT_MONTH)}"
)
source_df = spark.sql(SOURCE_SQL)
SOURCE_ROWS = source_df.count()  # Also verifies that the pinned data files are readable.
if SOURCE_ROWS == 0:
    raise RuntimeError("No rows for this month and version. Stop; an empty sample is not a pass.")
SCHEMA_HASH = sha256(source_df.schema.json().encode()).hexdigest()
if spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id").first()["id"] != SOURCE_TABLE_ID:
    raise RuntimeError("Source table identity changed during setup. Start a new review.")
DATA_TYPES = {field.name: field.dataType for field in source_df.schema.fields}
print(json.dumps({
    "source": SOURCE_TABLE, "source_version": PINNED_VERSION,
    "month": REPORT_MONTH, "source_rows": SOURCE_ROWS,
    "source_columns": len(DATA_TYPES), "schema_sha256": SCHEMA_HASH,
    "run_started_utc": RUN_STARTED_UTC,
    "spark_session_timezone": spark.conf.get("spark.sql.session.timeZone"),
    "business_validation": "PENDING", "agent_error_attribution": "NOT_ASSESSED",
}, indent=2))
display(history.filter(F.col("version") == PINNED_VERSION).select("version", "timestamp", "operation"))
```

## Cell 2: Record every column and check visible constraints

```python
# DBTITLE 1,2. Record every column and check visible constraints
KEY_COLUMNS = ["month", "week_num", "customer", "sales_rep", "agreement", "tcr", "service", "category"]
missing_columns = sorted(set(KEY_COLUMNS) - set(DATA_TYPES))
if missing_columns:
    raise RuntimeError(f"Required grouping columns are absent: {missing_columns}")
if any(not isinstance(DATA_TYPES[name], T.StringType) for name in KEY_COLUMNS):
    raise TypeError("The grouping-column types changed. Review the schema before comparing with prior runs.")

def missing_key_expression(keys):
    return reduce(lambda a, b: a | b, [
        F.col(ident(k)).isNull() | (F.trim(F.col(ident(k))) == "") for k in keys
    ])

def invalid_number_expression(name):
    if isinstance(DATA_TYPES[name], (T.DoubleType, T.FloatType)):
        value = F.col(ident(name))
        return F.isnan(value) | (F.abs(value) == F.lit(float("inf")))
    return F.lit(False)

def count_matching_rows(condition):
    # Count true matches. NULL is not a match and remains visible in null_rows.
    return F.count(F.when(condition, F.lit(1)))

quality_expressions = []
for position, (name, dtype) in enumerate(DATA_TYPES.items()):
    value = F.col(ident(name))
    quality_expressions.extend([
        count_matching_rows(value.isNull()).alias(f"null_{position}"),
        count_matching_rows(invalid_number_expression(name)).alias(f"invalid_{position}"),
        count_matching_rows((F.trim(value) == "") if isinstance(dtype, T.StringType) else F.lit(False)).alias(f"blank_{position}"),
    ])
quality = source_df.agg(*quality_expressions).first().asDict()
column_inventory = [
    (i + 1, name, dtype.simpleString(), int(quality[f"null_{i}"]),
     int(quality[f"blank_{i}"]), int(quality[f"invalid_{i}"]))
    for i, (name, dtype) in enumerate(DATA_TYPES.items())
]
display(spark.createDataFrame(column_inventory,
    "column_number int, column_name string, data_type string, null_rows long, blank_rows long, non_finite_rows long"))

catalog, schema_name, table_name = SOURCE_TABLE.split(".")
try:
    constraints = spark.sql(f"""
      SELECT constraint_name, constraint_type
      FROM {ident(catalog)}.information_schema.table_constraints
      WHERE table_schema = {literal(schema_name)} AND table_name = {literal(table_name)}
      ORDER BY constraint_type, constraint_name
    """).collect()
    print("Current visible constraint metadata (not historical DDL):")
    print(json.dumps([r.asDict() for r in constraints], indent=2))
    print("No visible constraint is not proof of a missing business identity; PK/FK declarations do not prove data quality.")
except Exception as error:
    print(f"Constraint metadata unavailable ({type(error).__name__}). Primary-key declaration status remains UNKNOWN.")

# Exact source names remain unchanged. This counts possible cleaning collisions; it never merges them.
customer_names = source_df.select("customer").distinct()
name_collision_groups = (
    customer_names.filter(F.col("customer").isNotNull())
    .groupBy(F.upper(F.trim("customer")).alias("comparison_only_name"))
    .count().filter(F.col("count") > 1).count()
)
print(f"Customer-name groups that would merge after upper/trim: {name_collision_groups}")
print("Customer names are source attributes, not verified customer IDs. Equal names can still represent different entities.")
```

## Cell 3: Define a guarded numerical comparison

```python
# DBTITLE 1,3. Define a guarded numerical comparison
def build_metric_query(source_sql, keys, metric, scope_name):
    """Diagnostic SQL. A sole value is used only after consistency and completeness checks."""
    group_keys = ", ".join(ident(k) for k in keys)
    value = ident(metric)
    missing = " OR ".join(f"({ident(k)} IS NULL OR TRIM({ident(k)}) = '')" for k in keys)
    non_finite = f"LOWER(CAST({value} AS STRING)) IN ('nan', 'infinity', '-infinity', '+infinity', 'inf', '-inf', '+inf')"
    return f"""WITH source_data AS (
  {source_sql}
), grouped AS (
  SELECT {group_keys},
         COUNT(*) AS physical_rows,
         COUNT(DISTINCT {value}) AS non_null_variants,
         SUM(CASE WHEN {value} IS NULL THEN 1 ELSE 0 END) AS null_rows,
         SUM(CASE WHEN {non_finite} THEN 1 ELSE 0 END) AS non_finite_rows,
         SUM(CASE WHEN {missing} THEN 1 ELSE 0 END) AS missing_key_rows,
         MIN({value}) AS sole_value_if_consistent
  FROM source_data
  GROUP BY {group_keys}
), checked AS (
  SELECT *,
         non_null_variants + CASE WHEN null_rows > 0 THEN 1 ELSE 0 END AS variants_including_null,
         CASE WHEN non_null_variants = 1 AND null_rows = 0
                   AND non_finite_rows = 0 AND missing_key_rows = 0
              THEN 1 ELSE 0 END AS eligible
  FROM grouped
), summary AS (
  SELECT COALESCE(SUM(physical_rows), 0) AS source_rows,
         COUNT(*) AS candidate_groups,
         COALESCE(SUM(physical_rows - 1), 0) AS rows_beyond_candidate_groups,
         COALESCE(SUM(CASE WHEN physical_rows > 1 THEN 1 ELSE 0 END), 0) AS repeated_groups,
         COALESCE(SUM(CASE WHEN variants_including_null > 1 THEN 1 ELSE 0 END), 0) AS conflicting_groups,
         COALESCE(SUM(CASE WHEN null_rows > 0 THEN 1 ELSE 0 END), 0) AS groups_with_null_metrics,
         COALESCE(SUM(null_rows), 0) AS null_metric_rows,
         COALESCE(SUM(missing_key_rows), 0) AS missing_key_rows,
         COALESCE(SUM(non_finite_rows), 0) AS non_finite_rows,
         COALESCE(SUM(eligible), 0) AS eligible_groups,
         COALESCE(SUM(CASE WHEN eligible = 0 THEN physical_rows ELSE 0 END), 0) AS excluded_source_rows,
         SUM(CASE WHEN eligible = 1 THEN sole_value_if_consistent END) AS eligible_candidate_subtotal
  FROM checked
), raw_total AS (
  SELECT SUM({value}) AS raw_source_sum FROM source_data
), result AS (
  SELECT summary.*,
         CASE WHEN non_finite_rows = 0
                   AND LOWER(CAST(raw_source_sum AS STRING)) NOT IN ('nan', 'infinity', '-infinity', '+infinity', 'inf', '-inf', '+inf')
              THEN raw_source_sum END AS raw_non_null_sum,
         CASE WHEN source_rows > 0 AND eligible_groups = candidate_groups
                   AND LOWER(CAST(raw_source_sum AS STRING)) NOT IN ('nan', 'infinity', '-infinity', '+infinity', 'inf', '-inf', '+inf')
                   AND LOWER(CAST(eligible_candidate_subtotal AS STRING)) NOT IN ('nan', 'infinity', '-infinity', '+infinity', 'inf', '-inf', '+inf')
              THEN eligible_candidate_subtotal END AS candidate_grain_total,
         CASE WHEN source_rows = 0 THEN 'EMPTY_SCOPE'
              WHEN conflicting_groups > 0 OR non_finite_rows > 0 THEN 'BLOCKED_CONFLICT_OR_INVALID_VALUE'
              WHEN LOWER(CAST(raw_source_sum AS STRING)) IN ('nan', 'infinity', '-infinity', '+infinity', 'inf', '-inf', '+inf')
                OR LOWER(CAST(eligible_candidate_subtotal AS STRING)) IN ('nan', 'infinity', '-infinity', '+infinity', 'inf', '-inf', '+inf')
                THEN 'BLOCKED_NON_FINITE_AGGREGATE'
              WHEN missing_key_rows > 0 OR null_metric_rows > 0 THEN 'BLOCKED_INCOMPLETE_KEYS_OR_VALUES'
              ELSE 'CONSISTENT_CANDIDATE_NOT_BUSINESS_VALIDATED' END AS diagnostic_status
  FROM summary CROSS JOIN raw_total
)
SELECT {literal(scope_name)} AS candidate_scope, {literal(metric)} AS metric,
       result.*, raw_non_null_sum - candidate_grain_total AS raw_minus_candidate,
       'PENDING_IDENTITY_GRAIN_AND_ADDITIVITY_VALIDATION' AS business_status
FROM result"""

print("Helper ready. MIN only retrieves the sole observed value after checks; it never resolves a conflicting group.")
```

## Cell 4: List the hypotheses before looking at totals

```python
# DBTITLE 1,4. List the hypotheses before looking at totals
CANDIDATE_SCOPES = {
    "ALLOCATION": ["month", "week_num", "customer", "sales_rep", "agreement", "tcr", "service", "category"],
    "BOOKING": ["month", "customer", "agreement", "week_num", "service", "tcr"],
    "COMMITMENT": ["month", "customer", "agreement", "week_num", "service"],
    "MONTHLY": ["month", "customer", "sales_rep", "agreement", "service"],
    "AGREEMENT_CONTEXT": ["month", "agreement"],
}
# These lists come from the earlier source mapping. They are hypotheses, not approved keys or formulas.
HYPOTHESES = {
    "ALLOCATION": "sail_week reviewed_teu original_teu final_teu tcr_cutoff days_to_cutoff is_volume_without_csal is_past_booking_window is_swap_donor swappable_teu is_swap_receiver swap_tier total_donor_teu_available issue_priority_score priority_level issue_count primary_issue".split(),
    "BOOKING": "vessel_voyage cy_cutoff confirmed_teu cancelled_teu rejected_teu pended_teu terminated_teu no_show_teu booked_teu booking_rate cancellation_rate rejection_rate booking_count total_booking_count avg_booking_lead_days booking_status_reasons pol pod fnd is_low_booking is_high_cancellation is_above_csal is_high_rejection swap_demand_teu".split(),
    "COMMITMENT": ["total_reviewed_teu"],
    "MONTHLY": "monthly_reviewed_teu monthly_total_reviewed_teu monthly_confirmed_teu monthly_cancelled_teu monthly_rejected_teu monthly_booked_teu monthly_booking_rate monthly_cancellation_rate monthly_rejection_rate is_low_booking_monthly is_high_cancellation_monthly is_high_rejection_monthly is_above_csal_monthly is_volume_without_csal_monthly primary_issue_monthly".split(),
    "AGREEMENT_CONTEXT": "case_incidentid case_title case_owner case_status case_created_on case_modified_on case_resolution_action case_resolution_date case_link sc_mqc ctd_vol ctd_prorated_mqc mqc_fulfillment_pct mqc_status".split(),
}
HYPOTHESIS_FOR = {column: scope for scope, columns in HYPOTHESES.items() for column in columns}
AMOUNTS_TO_COMPARE = set("""
reviewed_teu original_teu final_teu swappable_teu total_donor_teu_available
confirmed_teu cancelled_teu rejected_teu pended_teu terminated_teu no_show_teu booked_teu
booking_count total_booking_count swap_demand_teu total_reviewed_teu
monthly_reviewed_teu monthly_total_reviewed_teu monthly_confirmed_teu monthly_cancelled_teu
monthly_rejected_teu monthly_booked_teu sc_mqc ctd_vol ctd_prorated_mqc
""".split())
print("No target row reduction, preferred total or expected number of failures is specified.")
print("Month is included in every candidate. With one month selected it does not change the grouping.")
print("Agreement context means context observed in this sample, not proof of contract history or an enterprise agreement key.")
display(spark.createDataFrame([(n, " + ".join(k)) for n, k in CANDIDATE_SCOPES.items()],
                             "candidate_scope string, grouping_columns string"))
```

## Cell 5: Test every current column against every candidate scope

```python
# DBTITLE 1,5. Test every current column against every candidate scope
def profile_scope(scope_name, keys):
    scalar_columns = [n for n, d in DATA_TYPES.items()
                      if not isinstance(d, (T.ArrayType, T.MapType, T.StructType, T.BinaryType))]
    expressions = [F.count(F.lit(1)).alias("_rows"),
                   F.sum(missing_key_expression(keys).cast("long")).alias("_missing_keys")]
    for i, name in enumerate(scalar_columns):
        value = F.col(ident(name))
        # DISTINCT ignores NULL. Add a separate NULL state instead of a magic text sentinel.
        expressions.append((F.countDistinct(value) + F.max(value.isNull().cast("long"))).alias(f"v{i}"))
    grouped = source_df.groupBy(*keys).agg(*expressions)
    totals = grouped.agg(
        F.count(F.lit(1)).alias("groups"),
        F.sum(F.col("_rows") - 1).alias("rows_beyond_groups"),
        F.sum(F.col("_missing_keys")).alias("missing_key_rows"),
        F.sum((F.col("_rows") > 1).cast("long")).alias("repeated_groups"),
        *[F.sum((F.col(f"v{i}") > 1).cast("long")).alias(f"conflict{i}") for i in range(len(scalar_columns))],
    ).first().asDict()
    return [
        (scope_name, name, SOURCE_ROWS, int(totals["groups"]), int(totals["repeated_groups"]),
         int(totals["rows_beyond_groups"]), int(totals["missing_key_rows"]),
         int(totals[f"conflict{i}"]), "GROUPING_ATTRIBUTE" if name in keys else "TESTED_OBSERVATION")
        for i, name in enumerate(scalar_columns)
    ]

profile_rows = []
for scope_name, keys in CANDIDATE_SCOPES.items():
    print(f"Checking all scalar columns at {scope_name}...")
    profile_rows.extend(profile_scope(scope_name, keys))
profile_schema = "candidate_scope string, column_name string, source_rows long, candidate_groups long, repeated_groups long, rows_beyond_candidate_groups long, missing_key_rows long, conflicting_groups long, role string"
scope_profiles_df = spark.createDataFrame(profile_rows, profile_schema)
display(scope_profiles_df.orderBy("candidate_scope", F.desc("conflicting_groups"), "column_name"))

profiles_by_pair = {(r[0], r[1]): r for r in profile_rows}
coverage_rows = []
for i, (name, dtype) in enumerate(DATA_TYPES.items()):
    proposed_scope = HYPOTHESIS_FOR.get(name)
    observed = profiles_by_pair.get((proposed_scope, name))
    if name in KEY_COLUMNS:
        scope_label, status, conflicts = "SOURCE_ATTRIBUTE", "IDENTITY_OR_CALENDAR_RULE_NOT_VERIFIED", None
    elif proposed_scope is None:
        scope_label, status, conflicts = "UNMAPPED", "NEEDS_MAPPING", None
    elif observed is None:
        scope_label, status, conflicts = proposed_scope, "UNSUPPORTED_TYPE_NEEDS_REVIEW", None
    else:
        scope_label, conflicts = proposed_scope, observed[7]
        status = "CONFLICT" if conflicts else "CONSTANT_IN_SAMPLE_ONLY"
    coverage_rows.append((i + 1, name, dtype.simpleString(), scope_label, status, conflicts))
display(spark.createDataFrame(coverage_rows,
    "column_number int, column_name string, data_type string, proposed_scope string, observation string, conflicting_groups long"))
print(f"Coverage inventory: {len(coverage_rows)} of {len(DATA_TYPES)} current columns; unmapped columns are shown explicitly.")
print("A constant flag or percentage is not automatically additive. A one-row group passes constancy by construction.")
```

## Cell 6: Compare candidate amount totals without hiding exclusions

```python
# DBTITLE 1,6. Compare candidate amount totals without hiding exclusions
numeric_types = (T.ByteType, T.ShortType, T.IntegerType, T.LongType, T.FloatType, T.DoubleType, T.DecimalType)
metric_queries = {}
numeric_result_frames = []
for metric in sorted(AMOUNTS_TO_COMPARE):
    if metric not in DATA_TYPES:
        print(f"NOT_TESTED: absent amount column {metric}")
        continue
    if not isinstance(DATA_TYPES[metric], numeric_types):
        print(f"NOT_TESTED: {metric} is not a supported numeric type")
        continue
    scope_name = HYPOTHESIS_FOR[metric]
    sql_text = build_metric_query(SOURCE_SQL, CANDIDATE_SCOPES[scope_name], metric, scope_name)
    metric_queries[metric] = sql_text
    # Run each native-type comparison independently. Stringify only the final display values
    # to prevent a union of different decimals/doubles from changing numerical precision.
    result = spark.sql(sql_text).collect()
    numeric_result_frames.append(spark.createDataFrame([
        tuple(None if value is None else str(value) for value in row) for row in result
    ], T.StructType([T.StructField(c, T.StringType(), True) for c in result[0].asDict()])))
    print(f"Compared {metric}")
if not numeric_result_frames:
    raise RuntimeError("No supported amount columns were available.")
numeric_review_df = reduce(lambda a, b: a.unionByName(b), numeric_result_frames)
display(numeric_review_df.orderBy("candidate_scope", "metric"))
print("candidate_grain_total is NULL when any key, metric, non-finite or consistency check blocks a full comparison.")
print("eligible_candidate_subtotal excludes the reported rows. Do not compare it with an agent's whole-portfolio total.")
print("raw_non_null_sum follows SQL SUM semantics; nulls are counted separately and are never replaced by zero.")
```

## Cell 7: Inspect one evidence case and test sensitivity to extra grouping columns

```python
# DBTITLE 1,7. Inspect one evidence case and test sensitivity to extra grouping columns
EVIDENCE_METRIC = "monthly_booked_teu"  # Change only this name to inspect another amount.
SHOW_GROUP_DETAILS = False  # Keep source-level examples inside the office environment.
if EVIDENCE_METRIC not in metric_queries:
    raise ValueError("Choose one of the amount names printed in cell 6.")

print(f"Source version {PINNED_VERSION}; month {REPORT_MONTH}; metric {EVIDENCE_METRIC}")
print(metric_queries[EVIDENCE_METRIC])
display(spark.sql(metric_queries[EVIDENCE_METRIC]))

base_scope = HYPOTHESIS_FOR[EVIDENCE_METRIC]
base_keys = CANDIDATE_SCOPES[base_scope]
extra_columns = [k for k in KEY_COLUMNS if k not in base_keys]
for extra in extra_columns:
    name = f"{base_scope}_PLUS_{extra.upper()}"
    sql_text = build_metric_query(SOURCE_SQL, base_keys + [extra], EVIDENCE_METRIC, name)
    display(spark.sql(sql_text))
print("Extra grouping columns test sensitivity. They are not automatically better keys or the recommended model.")
print("Use the printed SQL in a personal SQL editor cell for screenshots. Capture the code and the complete result, including blockers.")

if SHOW_GROUP_DETAILS:
    keys_sql = ", ".join(ident(k) for k in base_keys)
    metric_sql = ident(EVIDENCE_METRIC)
    detail_sql = f"""WITH source_data AS ({SOURCE_SQL})
    SELECT {keys_sql}, COUNT(*) AS physical_rows,
           COUNT(DISTINCT {metric_sql}) AS non_null_value_variants,
           SUM(CASE WHEN {metric_sql} IS NULL THEN 1 ELSE 0 END) AS null_metric_rows,
           MIN({metric_sql}) AS observed_minimum, MAX({metric_sql}) AS observed_maximum
    FROM source_data
    GROUP BY {keys_sql}
    HAVING COUNT(*) > 1
    ORDER BY non_null_value_variants DESC, physical_rows DESC, {keys_sql}
    LIMIT 10"""
    print(detail_sql)
    display(spark.sql(detail_sql))
    print("These are deterministic inspection examples, not a representative accuracy sample. Keep this detail in the office environment.")
```

## Cell 8: Finish with evidence limits and a source-change check

```python
# DBTITLE 1,8. Finish with evidence limits and a source-change check
ending_version = int(spark.sql(f"DESCRIBE HISTORY {TABLE_SQL} LIMIT 1").select("version").first()["version"])
ending_table_id = spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id").first()["id"]
if ending_table_id != SOURCE_TABLE_ID:
    raise RuntimeError("Source table identity changed. Do not combine these results; start a new review.")
print(json.dumps({
    "started_utc": RUN_STARTED_UTC, "finished_utc": datetime.now(timezone.utc).isoformat(),
    "pinned_source_version": PINNED_VERSION, "current_source_version_at_finish": ending_version,
    "month": REPORT_MONTH, "source_rows": SOURCE_ROWS, "source_columns": len(DATA_TYPES),
    "schema_sha256": SCHEMA_HASH,
    "all_reads_used_pinned_version": True,
    "source_advanced_since_start": ending_version != PINNED_VERSION,
    "production_agent_source_version": "NOT_VERIFIED",
    "business_identity_validation": "PENDING",
    "business_grain_and_formula_validation": "PENDING",
    "production_agent_test": "NOT_RUN_BY_THIS_NOTEBOOK",
    "production_error_causation": "NOT_ESTABLISHED_BY_TOTALS_ALONE",
}, indent=2))
print("Retain every planned outcome: consistent, conflicting, incomplete, unchanged and unsupported.")
print("Same-number agreement with a raw sum is an observed pattern; inspect the agent's SQL/tool trace before attributing a cause.")
print("The next evidence is the deployed producer grouping/join logic, identity rules, approved formulas and the agent's actual query scope.")
```
