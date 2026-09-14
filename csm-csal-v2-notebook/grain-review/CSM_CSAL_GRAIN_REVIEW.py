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

# COMMAND ----------
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

# COMMAND ----------
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

# COMMAND ----------
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

# COMMAND ----------
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

# COMMAND ----------
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

# COMMAND ----------
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

# COMMAND ----------
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

# COMMAND ----------
# DBTITLE 1,9. Inspect missing-value overlaps and swap context
required_state = ["TABLE_SQL", "SOURCE_TABLE_ID", "PINNED_VERSION", "REPORT_MONTH",
                  "SOURCE_ROWS", "SCHEMA_HASH", "ident", "literal"]
missing_state = [name for name in required_state if name not in globals()]
if missing_state:
    raise RuntimeError(
        "The earlier notebook session is unavailable. Run from Cell 1 using the "
        "previously recorded SOURCE_VERSION, then return to Cell 9."
    )

EXCEPTION_KEYS = ["month", "week_num", "customer", "sales_rep", "agreement", "tcr", "service", "category"]
MONTHLY_AMOUNTS = ["monthly_reviewed_teu", "monthly_total_reviewed_teu",
                   "monthly_confirmed_teu", "monthly_cancelled_teu",
                   "monthly_rejected_teu", "monthly_booked_teu"]
MQC_AMOUNTS = ["sc_mqc", "ctd_vol", "ctd_prorated_mqc"]
CONTEXT_COLUMNS = ["booked_teu", "is_volume_without_csal", "mqc_status",
                   "swap_tier", "is_swap_donor", "is_swap_receiver",
                   "swappable_teu", "swap_demand_teu", "total_donor_teu_available"]

# Read the recorded version explicitly; do not depend on an overwritten DataFrame.
exception_source_sql = (
    f"SELECT * FROM {TABLE_SQL} VERSION AS OF {PINNED_VERSION} "
    f"WHERE {ident('month')} = {literal(REPORT_MONTH)}"
)
if spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id").first()["id"] != SOURCE_TABLE_ID:
    raise RuntimeError("Source table identity changed. Start a separate review.")
exception_source_df = spark.sql(exception_source_sql)
required_columns = set(EXCEPTION_KEYS + MONTHLY_AMOUNTS + MQC_AMOUNTS + CONTEXT_COLUMNS)
absent_columns = sorted(required_columns - set(exception_source_df.columns))
if absent_columns:
    raise RuntimeError(f"Required columns are missing: {absent_columns}")
if sha256(exception_source_df.schema.json().encode()).hexdigest() != SCHEMA_HASH:
    raise RuntimeError("The schema differs from Cell 1. Do not combine these results.")
if exception_source_df.count() != SOURCE_ROWS:
    raise RuntimeError("The selected population differs from Cell 1. Stop and check the source.")

def build_exception_queries(source_sql, key_columns, monthly_columns, mqc_columns):
    """Return aggregate-only queries. No customer records or business totals are exported."""
    missing_labels = ", ".join(
        f"CASE WHEN {ident(k)} IS NULL OR TRIM({ident(k)}) = '' THEN {literal(k)} END"
        for k in key_columns
    )
    monthly_nulls = " + ".join(f"CASE WHEN {ident(c)} IS NULL THEN 1 ELSE 0 END" for c in monthly_columns)
    mqc_nulls = " + ".join(f"CASE WHEN {ident(c)} IS NULL THEN 1 ELSE 0 END" for c in mqc_columns)
    base = f"""WITH source_data AS ({source_sql}),
    labelled AS (
      SELECT *,
             COALESCE(NULLIF(CONCAT_WS(', ', {missing_labels}), ''), 'NONE') AS missing_grouping_columns,
             ({monthly_nulls}) AS monthly_amounts_null,
             ({mqc_nulls}) AS mqc_amounts_null,
             booked_teu IS NULL AS booked_teu_null
      FROM source_data
    )
    """
    pattern = "missing_grouping_columns, monthly_amounts_null, mqc_amounts_null, booked_teu_null"
    return {
        "1. Missing-value overlaps — includes the unaffected population": base + f"""
          SELECT {pattern}, COUNT(*) AS source_rows
          FROM labelled
          GROUP BY {pattern}
          ORDER BY source_rows DESC, {pattern}
        """,
        "2. Business context — affected rows only": base + f"""
          SELECT category, is_volume_without_csal, mqc_status,
                 {pattern}, COUNT(*) AS source_rows
          FROM labelled
          WHERE missing_grouping_columns <> 'NONE'
             OR monthly_amounts_null > 0 OR mqc_amounts_null > 0 OR booked_teu_null
          GROUP BY category, is_volume_without_csal, mqc_status, {pattern}
          ORDER BY source_rows DESC, category, is_volume_without_csal, mqc_status, {pattern}
        """,
        "3. Swap-tier availability — all source rows": f"""
          WITH source_data AS ({source_sql}), tier_context AS (
            SELECT *,
                   CASE WHEN swap_tier IS NULL THEN 'NULL'
                        WHEN TRIM(swap_tier) = '' THEN 'BLANK'
                        ELSE 'POPULATED' END AS swap_tier_state
            FROM source_data
          )
          SELECT swap_tier_state, is_swap_donor, is_swap_receiver,
                 COUNT(*) AS source_rows,
                 COUNT(CASE WHEN swappable_teu IS NULL THEN 1 END) AS swappable_null_rows,
                 COUNT(CASE WHEN swappable_teu <> 0 THEN 1 END) AS swappable_nonzero_rows,
                 COUNT(CASE WHEN swap_demand_teu IS NULL THEN 1 END) AS demand_null_rows,
                 COUNT(CASE WHEN swap_demand_teu <> 0 THEN 1 END) AS demand_nonzero_rows,
                 COUNT(CASE WHEN total_donor_teu_available IS NULL THEN 1 END) AS donor_available_null_rows,
                 COUNT(CASE WHEN total_donor_teu_available <> 0 THEN 1 END) AS donor_available_nonzero_rows
          FROM tier_context
          GROUP BY swap_tier_state, is_swap_donor, is_swap_receiver
          ORDER BY swap_tier_state, is_swap_donor, is_swap_receiver
        """,
    }

exception_queries = build_exception_queries(
    exception_source_sql, EXCEPTION_KEYS, MONTHLY_AMOUNTS, MQC_AMOUNTS
)
print(f"Version {PINNED_VERSION}; {REPORT_MONTH}; {SOURCE_ROWS:,} source rows.")
print("monthly_amounts_null counts missing fields out of 6; mqc_amounts_null counts missing fields out of 3.")
print("Each row belongs to one overlap pattern. Do not add marginal missing-value counts together.")
for label, query in exception_queries.items():
    print(label)
    display(spark.sql(query))

if spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id").first()["id"] != SOURCE_TABLE_ID:
    raise RuntimeError("Source table identity changed during the follow-up. Do not combine results.")
print(f"Cell 9 completed at {datetime.now(timezone.utc).isoformat()}.")
print("These outputs describe missingness and context. They do not establish a failed join or an agent error.")
print("A No CSAL label, an empty tier or a missing MQC value still needs its producer-rule explanation.")

# COMMAND ----------
# DBTITLE 1,10. Check the saved monthly and MQC rules
required_state = ["TABLE_SQL", "SOURCE_TABLE_ID", "PINNED_VERSION", "REPORT_MONTH",
                  "SOURCE_ROWS", "SCHEMA_HASH", "MONTHLY_AMOUNTS", "MQC_AMOUNTS"]
if any(name not in globals() for name in required_state):
    raise RuntimeError("Run the earlier cells using the recorded SOURCE_VERSION before Cell 10.")

rule_source_sql = (
    f"SELECT * FROM {TABLE_SQL} VERSION AS OF {PINNED_VERSION} "
    f"WHERE {ident('month')} = {literal(REPORT_MONTH)}"
)
if spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id").first()["id"] != SOURCE_TABLE_ID:
    raise RuntimeError("Source table identity changed. Start a separate review.")
rule_source_df = spark.sql(rule_source_sql)
if sha256(rule_source_df.schema.json().encode()).hexdigest() != SCHEMA_HASH:
    raise RuntimeError("The schema differs from Cell 1.")
if rule_source_df.count() != SOURCE_ROWS:
    raise RuntimeError("The source population differs from Cell 1.")

MONTHLY_JOIN_KEYS = ["month", "customer", "sales_rep", "agreement", "service"]
rule_types = {field.name: field.dataType for field in rule_source_df.schema.fields}
required_columns = MONTHLY_JOIN_KEYS + MONTHLY_AMOUNTS + MQC_AMOUNTS + ["mqc_status"]
if set(required_columns) - set(rule_types):
    raise RuntimeError("A required monthly or MQC column is missing.")
if not all(isinstance(rule_types[c], T.StringType) for c in MONTHLY_JOIN_KEYS + ["mqc_status"]):
    raise TypeError("The key or status types changed. Review them before replaying the saved rules.")
integer_types = (T.ByteType, T.ShortType, T.IntegerType, T.LongType)
if not all(isinstance(rule_types[c], integer_types) for c in MQC_AMOUNTS):
    raise TypeError("The saved MQC rule uses integer inputs. Review the changed types before replaying it.")

def build_rule_check_queries(source_sql, monthly_keys, monthly_columns, mqc_columns):
    """Test join semantics and replay a saved rule; neither is a production fix."""
    keys_sql = ", ".join(ident(k) for k in monthly_keys)
    equality_join = " AND ".join(f"s.{ident(k)} = e.{ident(k)}" for k in monthly_keys)
    null_safe_join = " AND ".join(f"s.{ident(k)} <=> n.{ident(k)}" for k in monthly_keys)
    null_labels = ", ".join(
        f"CASE WHEN s.{ident(k)} IS NULL THEN {literal(k)} END" for k in monthly_keys
    )
    blank_labels = ", ".join(
        f"CASE WHEN TRIM(s.{ident(k)}) = '' THEN {literal(k)} END" for k in monthly_keys
    )
    monthly_nulls = " + ".join(
        f"CASE WHEN s.{ident(c)} IS NULL THEN 1 ELSE 0 END" for c in monthly_columns
    )
    mqc_nulls = " + ".join(
        f"CASE WHEN {ident(c)} IS NULL THEN 1 ELSE 0 END" for c in mqc_columns
    )
    return {
        "1. Monthly join simulation — key index from the same Gold rows": f"""
          WITH source_data AS ({source_sql}),
          key_index AS (
            SELECT DISTINCT {keys_sql}, 1 AS present FROM source_data
          ), join_check AS (
            SELECT
              COALESCE(NULLIF(CONCAT_WS(', ', {null_labels}), ''), 'NONE') AS null_join_columns,
              COALESCE(NULLIF(CONCAT_WS(', ', {blank_labels}), ''), 'NONE') AS blank_join_columns,
              ({monthly_nulls}) AS monthly_amounts_null,
              e.present IS NOT NULL AS equality_match_in_simulation,
              n.present IS NOT NULL AS null_safe_match_in_simulation
            FROM source_data s
            LEFT JOIN key_index e ON {equality_join}
            LEFT JOIN key_index n ON {null_safe_join}
          )
          SELECT null_join_columns, blank_join_columns, monthly_amounts_null,
                 equality_match_in_simulation, null_safe_match_in_simulation,
                 COUNT(*) AS source_rows
          FROM join_check
          GROUP BY null_join_columns, blank_join_columns, monthly_amounts_null,
                   equality_match_in_simulation, null_safe_match_in_simulation
          ORDER BY source_rows DESC, null_join_columns, blank_join_columns, monthly_amounts_null
        """,
        "2. MQC status — saved rule replay, not a business correctness score": f"""
          WITH source_data AS ({source_sql}), inputs AS (
            SELECT mqc_status AS stored_mqc_status,
                   ({mqc_nulls}) AS mqc_amounts_null,
                   ctd_vol IS NULL OR ctd_prorated_mqc IS NULL AS ratio_inputs_missing,
                   COALESCE(ctd_prorated_mqc = 0, FALSE) AS denominator_is_zero,
                   COALESCE(ctd_vol < 0, FALSE) OR COALESCE(ctd_prorated_mqc < 0, FALSE)
                     AS negative_ratio_input,
                   (ctd_vol / NULLIF(ctd_prorated_mqc, 0)) * 100 AS saved_unrounded_pct
            FROM source_data
          ), replay AS (
            SELECT *,
                   CASE WHEN saved_unrounded_pct >= 100 THEN 'Ahead'
                        WHEN saved_unrounded_pct >= 80 THEN 'On Track'
                        WHEN saved_unrounded_pct >= 50 THEN 'Behind'
                        ELSE 'At Risk' END AS saved_rule_status
            FROM inputs
          ), compared AS (
            SELECT *,
                   CASE WHEN stored_mqc_status <=> saved_rule_status
                        THEN 'MATCHES_SAVED_RULE' ELSE 'DIFFERS_FROM_SAVED_RULE' END AS rule_comparison
            FROM replay
          )
          SELECT mqc_amounts_null, ratio_inputs_missing, denominator_is_zero,
                 negative_ratio_input, stored_mqc_status, saved_rule_status,
                 rule_comparison, COUNT(*) AS source_rows
          FROM compared
          GROUP BY mqc_amounts_null, ratio_inputs_missing, denominator_is_zero,
                   negative_ratio_input, stored_mqc_status, saved_rule_status, rule_comparison
          ORDER BY source_rows DESC, mqc_amounts_null, stored_mqc_status, saved_rule_status,
                   ratio_inputs_missing, denominator_is_zero, negative_ratio_input
        """,
    }

rule_check_queries = build_rule_check_queries(
    rule_source_sql, MONTHLY_JOIN_KEYS, MONTHLY_AMOUNTS, MQC_AMOUNTS
)
print(f"Version {PINNED_VERSION}; {REPORT_MONTH}; {SOURCE_ROWS:,} source rows.")
for label, query in rule_check_queries.items():
    result_df = spark.sql(query)
    result_rows = result_df.collect()
    if sum(row["source_rows"] for row in result_rows) != SOURCE_ROWS:
        raise RuntimeError(f"Row accounting failed for: {label}. Do not use this output.")
    print(label)
    display(spark.createDataFrame(result_rows, schema=result_df.schema))

# Show only writer references, not user identities, job names or arbitrary metadata.
print("3. Writer references recorded for the pinned Delta version")
try:
    writer_history = spark.sql(f"DESCRIBE HISTORY {TABLE_SQL}").filter(F.col("version") == PINNED_VERSION)
    visible_fields = [c for c in ["version", "timestamp", "operation", "notebook", "job"]
                      if c in writer_history.columns]
    writer_rows = writer_history.select(*visible_fields).limit(2).collect()
    if len(writer_rows) != 1:
        print("Writer references unavailable or ambiguous for this version.")
    else:
        writer = writer_rows[0].asDict(recursive=True)
        notebook_ref = writer.get("notebook") or {}
        job_ref = writer.get("job") or {}
        print(json.dumps({
            "version": writer.get("version"),
            "write_timestamp": str(writer.get("timestamp")),
            "timestamp_timezone": spark.conf.get("spark.sql.session.timeZone"),
            "operation": writer.get("operation"),
            "notebook_id": notebook_ref.get("notebookId"),
            "job_id": job_ref.get("jobId"),
            "job_run_id": job_ref.get("jobRunId"),
            "run_id": job_ref.get("runId"),
            "historical_producer_code_verified": False,
        }, indent=2))
except Exception as error:
    print(f"Writer metadata unavailable ({type(error).__name__}). Producer identity remains unverified.")

if spark.sql(f"DESCRIBE DETAIL {TABLE_SQL}").select("id").first()["id"] != SOURCE_TABLE_ID:
    raise RuntimeError("Source table identity changed during Cell 10. Do not combine the results.")
print(f"Cell 10 completed at {datetime.now(timezone.utc).isoformat()}.")
print("The monthly index is built from these same Gold keys, so null-safe matches are expected by construction.")
print("It does not reproduce the upstream monthly aggregate, recover missing amounts or validate unknown identities.")
print("An MQC rule match is not proof that the classification is appropriate or that this exact code was deployed.")
print("Use the writer references to inspect the producing run and its code. No data or agent configuration was changed.")
