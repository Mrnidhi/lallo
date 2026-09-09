# Sales AI V2 benchmark

Revision: `v2_readable_client_1`

**Execution paused:** the package setup changed a core Databricks connection library. Do not rerun setup or continue the benchmark until the personal notebook environment is corrected.

We are comparing the existing personal wide-table agent with the personal booking-scope agent. The tables and agents are already built. This notebook checks their answers; it does not redesign or modify production.

## How to use this file

Copy each Python block into the matching cell of your existing **09-sales-ai-v2-benchmark** notebook. Match the **cell title**, not a number shifted by temporary diagnostic cells. Keep the completed build notebook and earlier run outputs. Do not paste the Markdown headings into Python cells.

1. Run cells **1–6** in order. They load settings, check the data and calculate expected answers.
2. Run cells **7–11**. They save the test setup, prepare the client and check the scorer.
3. Run cell **12 once**. By default, it asks one question through A and B, not the full batch.
4. Use cell **13** to record the actual returned rows, then run cell **14** for the comparison. Continue one pair at a time.

Do not use **Run all**. If a cell fails, stop at that cell. Do not delete an evidence file or change a passed check just to continue.

## What changed

The custom HTTP request code is replaced by Databricks' supported Responses client. Retries are disabled, each question starts fresh, and failed requests retain their error type, failing step and elapsed time. One function records actual answers. The existing data checks, reference calculations and numeric scoring rules remain in place.

This is a **new client experiment**, not a recovery of the earlier uncertain request. It saves to `v2-benchmark-client-evidence.json` in your personal workspace. Leave `v2-benchmark-simple-evidence.json` and `v2-benchmark-evidence.json` unchanged. Earlier failures remain part of the project history, not evidence of successful runs.

Use an existing compatible notebook environment: `databricks-openai` 0.17 or later, with a supported `openai` version below 3. Cell 8 checks the installed client features. No separate API key is needed in the code.

## Setup | Compatibility issue found

Imports initially failed because `databricks_openai` was missing. Installing `databricks-openai==0.17.1` with `openai==2.26.0` completed, but Databricks reported that `databricks-connect` changed from `18.0.9` to `17.0.10`. That is a core runtime compatibility warning, not a successful benchmark check.

Execution stopped before Python restart or any further benchmark cell. The change is notebook-scoped. Production objects and saved evidence were not modified.

Do not repeat that installation, restart Python, force dependency resolution, or delete evidence to continue. The next step is to agree on restoring the original personal notebook environment and adapting the client to compatible existing libraries. The 14 code blocks below are preserved for reference; the current client setup is not cleared for execution.

References: [Databricks notebook-scoped libraries](https://docs.databricks.com/aws/en/libraries/notebooks-python-libraries) and [Databricks OpenAI package](https://pypi.org/project/databricks-openai/0.17.1/).

## What this batch covers

The full question bank still has **41 questions**. This batch has prepared reference calculations for **12 questions**: bank IDs **1–7, 15, 18, 20, 23 and 27**, mapped to C01–C07, D01, D04, D06, D09 and R01. Three repetitions through two agents give **72 planned runs**. The remaining 29 still need scoring support; the existing manual chats are useful evidence but are not automatically verified benchmark results.

Compare answer accuracy, consistency, available SQL and response time. Missing SQL or timing stays unavailable. Shared sources are live and checked for changes; managed-model equality and actual per-request warehouse use remain unverified. Do not claim the table design alone caused a difference.

Only personal evidence files are written. Production objects, agents, enrichment, threshold values and swap logic stay unchanged. Keep returned customer rows, responses and evidence files out of Git.

## Notebook cells

## Cell 1 | Imports

Imports stay together. Run this first in the existing notebook environment.

```python
# Cell 1 | Imports
# Use the personal 09-sales-ai-v2-benchmark notebook; leave the completed build cells unchanged.
# Run these cells one at a time, starting here.

from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from importlib.metadata import version as package_version
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import inspect
import json
import math
import os
import re
import statistics
import tempfile
import time

from databricks.sdk import WorkspaceClient
from databricks_openai import DatabricksOpenAI
from pyspark.sql import functions as F, types as T

V2_BENCHMARK_READY = False
print("Imports ready. Next: cell 2, settings.")
```

## Cell 2 | Set up the comparison

Both agents receive the same questions. The new evidence filename keeps earlier attempts intact.

```python
# Cell 2 | Set up the comparison
# Run at the start of a session. Cell 7 saves the setup; only cell 12 asks agents.

V2_BENCHMARK_READY = False
PERSONAL_OWNER = "jayarsr@oocl.com"
PERSONAL_SCHEMA = "usr.jayarsr"
BASELINE = PERSONAL_SCHEMA + ".src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23"
BASELINE_VERSION = 0  # Personal copy of original Gold v32. The suffix is a build label.
BOOKING_VIEW = PERSONAL_SCHEMA + ".agent_booking_risk_current_poc_v2_v23"
ENDPOINTS = {"A": "mas-3beadca0-endpoint", "B": "mas-6b7af80b-endpoint"}
WAREHOUSE_ID = "e01805775d74d241"
SOURCES = {
    "finance": "dev.sales_ai_assistant_gold.fincon_issues",
    "cases": "dev.sales_ai_assistant_gold.sales_ai_case_ledger",
    "issues": "dev.sales_ai_assistant_gold.sales_ai_case_issues",
    "roster": "dev.sales_ai_assistant_gold.sales_ai_roster",
    "outlook": "dev.sales_ai_assistant_gold.tea_deliverables",
    "detail": "dev.crmi_gold.csal_teu_performance",
}
CSM_DEPENDENCIES = [BASELINE] + [
    PERSONAL_SCHEMA + "." + name + "_poc_v2_v23"
    for name in ["fact_booking_summary", "fact_commitment", "dim_customer",
                 "dim_agreement", "dim_week", "dim_service", "dim_tcr"]
]
SCOPE = "customer agreement week_num service tcr".split()
BOOKING_MEASURES = "confirmed_teu cancelled_teu rejected_teu pended_teu terminated_teu no_show_teu booked_teu".split()
MEASURES = BOOKING_MEASURES + ["total_reviewed_teu"]
FLAGS = "is_low_booking is_high_cancellation is_high_rejection is_above_csal".split()
FILTERS = {"week": "2026WK22", "service": "PVCS", "tcr": "HKG"}
MISSING_CUSTOMER = "CSM_POC_V2_NO_MATCH_20260901"
DAILY_OUTLOOK_TASK = "DAILY_OUTLOOK"  # Verify the task_name value, not deliverable_type.
QUESTION_IDS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "D01", "D04", "D06", "D09", "R01"]
REPETITIONS = 3
WORDING_VERSION = "v2_question_wording_2"
CODE_VERSION = "v2_readable_client_1"
EXPERIMENT_LABEL = "sales_ai_v2_first12_client_01"

# Leave these empty to select usable examples within each source.
# A matching name in two domains is not proof of a shared identity.
SALES_OVERRIDES = {"finance": None, "cases": None, "no_issues": None, "outlook": None}

# Both saved endpoint examples use the Responses input format.
REQUEST_CONTRACT = {"A": "input", "B": "input"}
MAX_TRIALS_THIS_RUN = 2  # One question through A and B per run of cell 12.
HTTP_TIMEOUT_SECONDS = 180
# This is a separate client comparison, not a retry of the old uncertain request.
# Keep both previous evidence files unchanged; do not copy their trials here.
EVIDENCE_PATH = Path("/Workspace/Users/jayarsr@oocl.com/Sales AI EDA/v2-benchmark-client-evidence.json")

print("Plan: 12 questions × 2 supervisors × 3 repetitions = 72 trials.")
print("No enrichment, table rebuilds, new agents or production writes are included.")
print("Next: run cells 3-6 individually to prepare the reference answers.")
print("All 41 questions remain the full target; these 12 are the ready-to-test subset.")
```

## Cell 3 | Read-only source checks

Read-only checks for source versions, column types and row keys.

```python
# Cell 3 | Read-only source checks
# Check source versions, column types, and row keys before preparing expected answers.

V2_BENCHMARK_READY = False
PREPARATION_STAMPS = {}
assert "spark" in globals(), "Run this in the existing personal Databricks notebook."
assert spark.sql("SELECT current_user()").first()[0].lower() == PERSONAL_OWNER
assert "args" in inspect.signature(spark.sql).parameters, (
    "This code requires a Spark runtime with named SQL parameters."
)
SESSION_TIME_ZONE = spark.conf.get("spark.sql.session.timeZone")
# Keep the existing timezone; include it in the preparation fingerprint.
print("Spark session timezone:", SESSION_TIME_ZONE)


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "asDict"):
        return value.asDict(recursive=True)
    raise TypeError("Unsupported evidence value: " + type(value).__name__)


def stable_json(value):
    return json.dumps(
        value,
        default=json_value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def fingerprint(value):
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def preparation_inputs():
    # Only settings that affect the prepared answers or benchmark setup belong here.
    return {
        "owner": PERSONAL_OWNER,
        "baseline": BASELINE,
        "version": BASELINE_VERSION,
        "view": BOOKING_VIEW,
        "sources": SOURCES,
        "dependencies": CSM_DEPENDENCIES,
        "scope": SCOPE,
        "measures": MEASURES,
        "booking_measures": BOOKING_MEASURES,
        "flags": FLAGS,
        "filters": FILTERS,
        "missing_customer": MISSING_CUSTOMER,
        "outlook_task": DAILY_OUTLOOK_TASK,
        "sales_overrides": SALES_OVERRIDES,
        "questions": QUESTION_IDS,
        "repetitions": REPETITIONS,
        "wording_version": WORDING_VERSION,
        "code_version": CODE_VERSION,
        "endpoints": ENDPOINTS,
        "warehouse": WAREHOUSE_ID,
        "timezone": SESSION_TIME_ZONE,
    }


def invalidate_preparation(stage):
    # Rerunning a stage also invalidates every later stage.
    stages = ["sources", "booking", "shared", "questions"]
    for name in stages[stages.index(stage):]:
        PREPARATION_STAMPS.pop(name, None)


def preparation_stamp(stage, payload):
    PREPARATION_STAMPS[stage] = {
        "inputs": fingerprint(preparation_inputs()),
        "content": fingerprint(payload),
    }


def require_preparation(stage, payload):
    expected = {"inputs": fingerprint(preparation_inputs()), "content": fingerprint(payload)}
    assert PREPARATION_STAMPS.get(stage) == expected, (
        "Preparation is missing or has changed at stage: " + stage
        + ". Rerun the preceding preparation cells in order."
    )


def booking_payload():
    ids = ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
    return {
        "expected": {key: GT.get(key) for key in ids},
        "sql": {key: GT_SQL.get(key) for key in ids},
        "parameters": {key: GT_PARAMETERS.get(key) for key in ids},
        "contracts": {key: CONTRACTS.get(key) for key in ids},
        "lookup": LOOKUP_FIXTURE,
        "source_state": SOURCE_MARKER,
    }


def ground_truth_payload():
    return {
        "expected": GT,
        "sql": GT_SQL,
        "parameters": GT_PARAMETERS,
        "contracts": CONTRACTS,
        "lookup": LOOKUP_FIXTURE,
        "sales": SALES_FIXTURES,
        "source_state": SOURCE_MARKER,
    }


def review_payload():
    return {
        "ground_truth": ground_truth_payload(),
        "prompts": PROMPTS,
        "traceability": TRACEABILITY,
        "method_version": METHOD_VERSION,
        "inputs": preparation_inputs(),
    }


def require_columns(frame, names, label):
    missing = set(names) - set(frame.columns)
    assert not missing, label + " is missing columns: " + ", ".join(sorted(missing))


def assert_unique(frame, keys, label):
    duplicates = frame.groupBy(*keys).count().filter(F.col("count") > 1).limit(1).count()
    assert duplicates == 0, (
        label + ": multiple rows share the expected key. Check the source; do not drop rows arbitrarily."
    )


def assert_finite(frame, names, label):
    bad = F.lit(False)
    for name in names:
        val = F.col(name).cast("double")
        bad = bad | F.coalesce(F.isnan(val) | val.isin(float("inf"), float("-inf")), F.lit(False))
    assert frame.filter(bad).limit(1).count() == 0, label + ": a measure contains NaN or infinity."


def source_markers():
    # Capture table identity, version, schema, and the booking-view definition.
    records = {}
    for name in sorted(set(CSM_DEPENDENCIES + list(SOURCES.values()))):
        detail = spark.sql("DESCRIBE DETAIL " + name).select("id", "format").first()
        assert detail["format"].lower() == "delta", "Version evidence unavailable for " + name
        history = spark.sql("DESCRIBE HISTORY " + name).select("version").orderBy(F.desc("version")).first()
        records[name] = {
            "id": detail["id"],
            "version": int(history["version"]),
            "schema_sha256": fingerprint(spark.table(name).schema.jsonValue()),
        }
    definition = spark.sql("SHOW CREATE TABLE " + BOOKING_VIEW).first()[0]
    return {"tables": records, "booking_view_sha256": fingerprint(definition)}


SOURCE_MARKER = source_markers()
assert SOURCE_MARKER["tables"][BASELINE]["version"] == BASELINE_VERSION, (
    "The baseline version has changed. Check BASELINE_VERSION before continuing."
)
BASE = spark.read.option("versionAsOf", BASELINE_VERSION).table(BASELINE)
AFTER = spark.table(BOOKING_VIEW)
require_columns(
    BASE,
    SCOPE + MEASURES + FLAGS + ["booking_rate", "cancellation_rate", "rejection_rate"],
    "Baseline",
)
require_columns(
    AFTER,
    SCOPE + MEASURES + FLAGS + ["booking_pct", "cancellation_pct", "rejection_pct", "fulfillment_pct"],
    "Booking view",
)
for label, frame in [("Baseline", BASE), ("Booking view", AFTER)]:
    for name in SCOPE:
        assert isinstance(frame.schema[name].dataType, T.StringType), label + ": key type changed: " + name
    for name in MEASURES:
        assert isinstance(frame.schema[name].dataType, T.NumericType), label + ": measure is not numeric: " + name
    for name in FLAGS:
        assert isinstance(frame.schema[name].dataType, T.BooleanType), label + ": flag is not boolean: " + name
    assert_finite(frame, MEASURES, label)
for frame, fields in [
    (BASE, ["booking_rate", "cancellation_rate", "rejection_rate"]),
    (AFTER, ["booking_pct", "cancellation_pct", "rejection_pct", "fulfillment_pct"]),
]:
    for name in fields:
        assert isinstance(frame.schema[name].dataType, T.NumericType), "Rate is not numeric: " + name
    assert_finite(frame, fields, "Rates")
assert_unique(
    BASE.select(*(SCOPE + MEASURES + FLAGS + ["booking_rate", "cancellation_rate", "rejection_rate"])).distinct(),
    SCOPE,
    "Baseline values per booking scope",
)
assert_unique(AFTER, SCOPE, "Booking view")

# Each shared source keeps its own keys and data types.
SHARED = {
    domain: spark.table(name)
    for domain, name in SOURCES.items()
    if domain in {"finance", "cases", "issues", "outlook"}
}
REQUIRED = {
    "finance": "customer sales sales_full snapshot_date total_outstanding max_aging_days ar_severity overdue_invoices overdue_30_amount overdue_60_amount overdue_90_amount".split(),
    "cases": "case_id sales_name customer_name state severity recommendation data_as_of_ts".split(),
    "issues": ["case_id", "case_issue_id"],
    "outlook": "deliverable_id sales_name task_name deliverable_type is_current created_ts data_as_of".split(),
}
for domain, names in REQUIRED.items():
    require_columns(SHARED[domain], names, domain)
for domain, names in {
    "finance": ["customer", "sales", "sales_full", "ar_severity"],
    "cases": ["case_id", "sales_name", "customer_name", "state", "recommendation"],
    "issues": ["case_id", "case_issue_id"],
    "outlook": ["deliverable_id", "sales_name", "task_name", "deliverable_type"],
}.items():
    for name in names:
        assert isinstance(SHARED[domain].schema[name].dataType, T.StringType), domain + ": unexpected text type: " + name
for domain, names in {
    "cases": ["data_as_of_ts"],
    "outlook": ["created_ts", "data_as_of"],
}.items():
    for name in names:
        assert SHARED[domain].schema[name].dataType.typeName() in {"timestamp", "timestamp_ntz"}, (
            domain + ": timestamp type changed: " + name
        )
assert isinstance(SHARED["outlook"].schema["is_current"].dataType, T.BooleanType)
assert isinstance(SHARED["finance"].schema["snapshot_date"].dataType, T.DateType)
for domain, columns in {
    "finance": [
        "total_outstanding", "max_aging_days", "overdue_invoices",
        "overdue_30_amount", "overdue_60_amount", "overdue_90_amount",
    ],
    "cases": ["severity"],
}.items():
    for column in columns:
        assert isinstance(SHARED[domain].schema[column].dataType, T.NumericType), column + " must be numeric."
    assert_finite(SHARED[domain], columns, domain)
for domain, key in [("cases", "case_id"), ("outlook", "deliverable_id")]:
    assert SHARED[domain].filter(F.col(key).isNull() | (F.trim(F.col(key)) == "")).limit(1).count() == 0
    assert_unique(SHARED[domain], [key], domain)
assert source_markers() == SOURCE_MARKER, "Sources changed during these checks. Rerun cell 3."
preparation_stamp("sources", SOURCE_MARKER)
print("Source checks passed. Next: cell 4, booking expected answers.")
```

## Cell 4 | Independent booking answers

Calculate booking reference answers through independent data and SQL paths. Keep existing metric definitions.

```python
# Cell 4 | Independent booking answers
# Compare baseline SQL, baseline DataFrames, and the booking view for C01-C07.

V2_BENCHMARK_READY = False
assert "PREPARATION_STAMPS" in globals(), "Run notebook cell 3 successfully first."
invalidate_preparation("booking")
require_preparation("sources", SOURCE_MARKER)
GT = {}
GT_SQL = {}
GT_PARAMETERS = {}
CONTRACTS = {}
LOOKUP_FIXTURE = None
# SQL uses the versioned table name; DataFrame checks use BASE from cell 3.
assert (
    isinstance(BASELINE, str)
    and BASELINE == "usr.jayarsr.src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23"
)
assert (
    isinstance(BASELINE_VERSION, int)
    and not isinstance(BASELINE_VERSION, bool)
    and BASELINE_VERSION >= 0
)
baseline_relation = BASELINE + " VERSION AS OF " + str(BASELINE_VERSION)
scope_order_sql = ", ".join(name + " ASC NULLS LAST" for name in SCOPE)
scope_order = [F.col(name).asc_nulls_last() for name in SCOPE]
scope_filter = (F.col("week_num") == FILTERS["week"]) & (F.col("service") == FILTERS["service"])
valid_keys = F.lit(True)
for name in SCOPE:
    valid_keys = valid_keys & F.col(name).isNotNull() & (F.trim(F.col(name).cast("string")) != "")
all_names = SCOPE + MEASURES + FLAGS + ["booking_rate", "cancellation_rate", "rejection_rate"]
base_scopes = BASE.select(*all_names).distinct().filter(scope_filter)
after_scopes = AFTER.filter(scope_filter)
ratio = F.when(
    F.col("total_reviewed_teu") > 0,
    F.col("confirmed_teu").cast("double") / F.col("total_reviewed_teu") * 100,
)
base_scopes = base_scopes.withColumn("fulfillment_pct", ratio)
for source, target in [
    ("booking_rate", "booking_pct"),
    ("cancellation_rate", "cancellation_pct"),
    ("rejection_rate", "rejection_pct"),
]:
    base_scopes = base_scopes.withColumn(target, F.col(source))
    after_scopes = after_scopes.withColumn(target, F.round(F.col(target), 2))


def comparable_rows(rows, precision):
    # Normalize numeric storage types without changing NULLs or row order.
    result = []
    for row in rows:
        normalized = dict(row)
        for column, places in precision.items():
            value = row.get(column)
            if value is not None:
                value = Decimal(str(value))
                assert value.is_finite(), "Non-finite expected value."
                if places is not None:
                    value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
                normalized[column] = value
        result.append(normalized)
    return result


def keep_answer(qid, sql, parameters, reference, view_answer, columns, precision):
    sql_rows = [row.asDict() for row in spark.sql(sql, args=parameters).collect()]
    independent_rows = [row.asDict() for row in reference.select(*columns).collect()]
    after_rows = [row.asDict() for row in view_answer.select(*columns).collect()]
    assert comparable_rows(sql_rows, precision) == comparable_rows(independent_rows, precision), (
        qid + ": SQL and independent DataFrame answers differ."
    )
    assert comparable_rows(independent_rows, precision) == comparable_rows(after_rows, precision), (
        qid + ": reference and comparison answers differ."
    )
    assert len(sql_rows) <= 20
    GT[qid] = {"answer": sql_rows}
    GT_SQL[qid] = {"answer": sql}
    GT_PARAMETERS[qid] = parameters
    CONTRACTS[qid] = {"answer": {"columns": columns, "precision": precision}}
    print(qid, "expected rows checked:", len(sql_rows))


common_cte = (
    "WITH scoped AS (SELECT DISTINCT " + ", ".join(all_names) + " FROM " + baseline_relation +
    " WHERE week_num = :week AND service = :service), ranked AS (SELECT *, "
    "CASE WHEN total_reviewed_teu > 0 THEN CAST(confirmed_teu AS DOUBLE) / total_reviewed_teu * 100 END AS fulfillment_pct, "
    "booking_rate AS booking_pct, cancellation_rate AS cancellation_pct, rejection_rate AS rejection_pct FROM scoped) "
)
numeric_teu = {name: None for name in MEASURES}
# C01-C05: use the same filters, NULL handling, and tie-break order in each path.
cases = [
    ("C01", None, "fulfillment_pct", False, ["confirmed_teu", "total_reviewed_teu", "fulfillment_pct"]),
    ("C02", "is_low_booking", "fulfillment_pct", False, ["confirmed_teu", "booked_teu", "total_reviewed_teu"]),
    ("C03", "is_high_cancellation", "cancellation_pct", True, ["cancelled_teu", "booked_teu", "cancellation_pct"]),
    ("C04", "is_high_rejection", "rejection_pct", True, ["rejected_teu", "booked_teu", "rejection_pct"]),
    ("C05", "is_above_csal", "booking_pct", True, ["booked_teu", "confirmed_teu", "total_reviewed_teu", "booking_pct"]),
]
for qid, flag, metric, descending, values in cases:
    columns = ["customer", "agreement", "tcr"] + values
    if flag:
        condition = F.col(flag) == True
        where_sql = flag + " = true"
    else:
        condition = valid_keys & F.col("confirmed_teu").isNotNull() & (F.col("total_reviewed_teu") > 0)
        where_sql = " AND ".join(
            name + " IS NOT NULL AND trim(CAST(" + name + " AS STRING)) <> ''"
            for name in SCOPE
        )
        where_sql += " AND confirmed_teu IS NOT NULL AND total_reviewed_teu > 0"
    ordering = (
        [F.col(metric).desc_nulls_last()] if descending else [F.col(metric).asc_nulls_last()]
    ) + scope_order
    ref = base_scopes.filter(condition).orderBy(*ordering).limit(20)
    aft = after_scopes.filter(condition).orderBy(*ordering).limit(20)
    sql = common_cte + "SELECT " + ", ".join(columns) + " FROM ranked WHERE " + where_sql
    sql += " ORDER BY " + metric + (" DESC" if descending else " ASC") + " NULLS LAST, " + scope_order_sql + " LIMIT 20"
    precision = {name: numeric_teu.get(name, 6 if name == "fulfillment_pct" else 2) for name in values}
    keep_answer(
        qid, sql, {"week": FILTERS["week"], "service": FILTERS["service"]},
        ref, aft, columns, precision,
    )
    assert GT[qid]["answer"], qid + ": no rows match this ranking test. Check the selected scope."

# C06: select a repeated booking row with one complete, consistent set of measures.
present = F.lit(True)
for name in BOOKING_MEASURES:
    present = present & F.col(name).isNotNull()
candidates = (
    BASE.filter(scope_filter)
    .filter(F.col("tcr") == FILTERS["tcr"])
    .filter(valid_keys)
    .groupBy(*SCOPE)
    .agg(
        F.count("*").alias("physical_rows"),
        F.countDistinct(F.struct(*BOOKING_MEASURES)).alias("versions"),
        F.min(F.when(present, 1).otherwise(0)).alias("complete"),
    )
    .filter("physical_rows > 1 AND versions = 1 AND complete = 1")
)
selected = candidates.orderBy(*scope_order).limit(1).collect()
assert selected, "C06 needs a repeated booking row with complete, consistent measures; none matched."
LOOKUP_FIXTURE = {name: selected[0][name] for name in SCOPE}
condition = F.lit(True)
for name, value in LOOKUP_FIXTURE.items():
    condition = condition & F.col(name).eqNullSafe(F.lit(value))
lookup_sql = "SELECT DISTINCT " + ", ".join(BOOKING_MEASURES) + " FROM " + baseline_relation + " WHERE "
lookup_sql += " AND ".join(name + " = :" + name for name in SCOPE)
keep_answer(
    "C06", lookup_sql, LOOKUP_FIXTURE,
    base_scopes.filter(condition), after_scopes.filter(condition),
    BOOKING_MEASURES, {name: None for name in BOOKING_MEASURES},
)
assert len(GT["C06"]["answer"]) == 1

# C07: confirm that the missing-customer question really has no matching rows.
assert BASE.filter(F.col("customer") == MISSING_CUSTOMER).limit(1).count() == 0
assert AFTER.filter(F.col("customer") == MISSING_CUSTOMER).limit(1).count() == 0
GT["C07"] = {"answer": []}
GT_SQL["C07"] = {"answer": "SELECT DISTINCT customer, agreement, tcr FROM " + baseline_relation + " WHERE customer = :customer AND week_num = :week AND service = :service"}
GT_PARAMETERS["C07"] = {
    "customer": MISSING_CUSTOMER,
    "week": FILTERS["week"],
    "service": FILTERS["service"],
}
assert spark.sql(GT_SQL["C07"]["answer"], args=GT_PARAMETERS["C07"]).count() == 0
CONTRACTS["C07"] = {"answer": {"columns": ["customer", "agreement", "tcr"], "precision": {}}}
assert source_markers() == SOURCE_MARKER, (
    "Sources changed while preparing booking answers. Rerun cells 3 and 4."
)
preparation_stamp("booking", booking_payload())
print("C01-C07 expected answers checked. Next: cell 5, shared-source expected answers.")
```

## Cell 5 | Finance, cases, Daily Outlook and the two-domain question

Calculate the finance, case and Daily Outlook answers without mixing their customer identities.

```python
# Cell 5 | Finance, cases, Daily Outlook and the two-domain question
# Build expected answers from existing records; recommendations and deliverables are not executed.

V2_BENCHMARK_READY = False
assert "PREPARATION_STAMPS" in globals(), "Run notebook cells 3 and 4 successfully first."
invalidate_preparation("shared")
assert "booking" in PREPARATION_STAMPS, "Notebook cell 4 has not completed successfully."
require_preparation("booking", booking_payload())
# Clear prior shared answers so a failed rerun cannot leave stale results.
for question_id in ["D01", "D04", "D06", "D09", "R01"]:
    for answers in [GT, GT_SQL, GT_PARAMETERS, CONTRACTS]:
        answers.pop(question_id, None)
SALES_FIXTURES = None
latest_snapshot = SHARED["finance"].agg(F.max("snapshot_date").alias("latest")).first()["latest"]
assert latest_snapshot is not None, "Finance has no dated snapshot."
finance_snapshot = SHARED["finance"].filter(F.col("snapshot_date") == F.lit(latest_snapshot))
zero_child_cases = SHARED["cases"].join(SHARED["issues"].select("case_id"), "case_id", "left_anti")
current_outlooks = SHARED["outlook"].filter(
    (F.col("task_name") == DAILY_OUTLOOK_TASK) & (F.col("is_current") == True)
)
assert current_outlooks.limit(1).count() == 1, (
    "No current Daily Outlook matched DAILY_OUTLOOK_TASK. Check the exact task_name."
)


def choose_rep(frame, column, override, label):
    candidates = frame.filter(F.col(column).isNotNull() & (F.trim(F.col(column)) != ""))
    if override is not None:
        assert isinstance(override, str) and override.strip()
        assert candidates.filter(F.col(column) == override).limit(1).count() == 1, (
            label + ": the selected representative has no matching rows."
        )
        return override
    # Choose the representative with the most matching rows; break ties by name.
    row = candidates.groupBy(column).count().orderBy(F.desc("count"), F.col(column).asc()).limit(1).collect()
    assert row, label + ": no representative has matching rows for this test."
    return row[0][column]


SALES_FIXTURES = {
    "finance": choose_rep(finance_snapshot, "sales", SALES_OVERRIDES["finance"], "D01"),
    "cases": choose_rep(SHARED["cases"], "sales_name", SALES_OVERRIDES["cases"], "D04"),
    "no_issues": choose_rep(zero_child_cases, "sales_name", SALES_OVERRIDES["no_issues"], "D06"),
    "outlook": choose_rep(current_outlooks, "sales_name", SALES_OVERRIDES["outlook"], "D09"),
}
# D01: rank outstanding balances within the latest finance snapshot.
finance_columns = "customer total_outstanding max_aging_days ar_severity snapshot_date".split()
finance_ties = [
    "customer", "sales", "sales_full", "snapshot_date", "overdue_invoices",
    "max_aging_days", "ar_severity", "overdue_30_amount", "overdue_60_amount", "overdue_90_amount",
]
finance_order = [F.col("total_outstanding").desc_nulls_last()] + [F.col(name).asc_nulls_last() for name in finance_ties]
finance_order_sql = "total_outstanding DESC NULLS LAST, " + ", ".join(name + " ASC NULLS LAST" for name in finance_ties)
fin_ref = finance_snapshot.filter(F.col("sales") == SALES_FIXTURES["finance"]).orderBy(*finance_order).limit(20)
fin_sql = "SELECT " + ", ".join(finance_columns) + " FROM " + SOURCES["finance"] + " WHERE snapshot_date = (SELECT max(snapshot_date) FROM " + SOURCES["finance"] + ") AND sales = :sales ORDER BY " + finance_order_sql + " LIMIT 20"
keep_answer(
    "D01", fin_sql, {"sales": SALES_FIXTURES["finance"]}, fin_ref, fin_ref,
    finance_columns, {"total_outstanding": 6, "max_aging_days": None},
)

# D04: highest-severity cases, with case_id breaking ties.
case_columns = "case_id customer_name state severity recommendation data_as_of_ts".split()
case_ref = (
    SHARED["cases"]
    .filter(F.col("sales_name") == SALES_FIXTURES["cases"])
    .orderBy(F.col("severity").desc_nulls_last(), F.col("case_id").asc())
    .limit(10)
)
case_sql = "SELECT " + ", ".join(case_columns) + " FROM " + SOURCES["cases"] + " WHERE sales_name = :sales ORDER BY severity DESC NULLS LAST, case_id ASC LIMIT 10"
keep_answer(
    "D04", case_sql, {"sales": SALES_FIXTURES["cases"]},
    case_ref, case_ref, case_columns, {"severity": 6},
)

# D06: retain cases with no matching issue rows.
no_issue_columns = ["case_id", "customer_name", "state"]
no_issue_ref = zero_child_cases.filter(F.col("sales_name") == SALES_FIXTURES["no_issues"]).orderBy("case_id").limit(20)
no_issue_sql = "SELECT c.case_id, c.customer_name, c.state FROM " + SOURCES["cases"] + " c WHERE c.sales_name = :sales AND NOT EXISTS (SELECT 1 FROM " + SOURCES["issues"] + " i WHERE i.case_id = c.case_id) ORDER BY c.case_id ASC LIMIT 20"
keep_answer(
    "D06", no_issue_sql, {"sales": SALES_FIXTURES["no_issues"]},
    no_issue_ref, no_issue_ref, no_issue_columns, {},
)
assert GT["D06"]["answer"], "D06 needs at least one case with no matching issue rows."

# D09: select the latest current Daily Outlook for this source's representative.
outlook_columns = ["deliverable_id", "created_ts", "data_as_of"]
outlook_ref = (
    current_outlooks
    .filter(F.col("sales_name") == SALES_FIXTURES["outlook"])
    .orderBy(F.col("created_ts").desc_nulls_last(), F.col("deliverable_id").asc())
    .limit(1)
)
outlook_sql = "SELECT deliverable_id, created_ts, data_as_of FROM " + SOURCES["outlook"] + " WHERE sales_name = :sales AND task_name = :task AND is_current = true ORDER BY created_ts DESC NULLS LAST, deliverable_id ASC LIMIT 1"
keep_answer(
    "D09", outlook_sql, {"sales": SALES_FIXTURES["outlook"], "task": DAILY_OUTLOOK_TASK},
    outlook_ref, outlook_ref, outlook_columns, {},
)
assert len(GT["D09"]["answer"]) == 1

# R01: return separate booking and finance lists, without joining customers.
r_csm_columns = ["customer", "agreement", "tcr", "cancellation_pct"]
r_fin_columns = ["customer", "total_outstanding"]
GT["R01"] = {
    "booking": [{name: row[name] for name in r_csm_columns} for row in GT["C03"]["answer"][:10]],
    "finance": [{name: row[name] for name in r_fin_columns} for row in GT["D01"]["answer"][:5]],
}
GT_SQL["R01"] = {
    "booking": GT_SQL["C03"]["answer"].removesuffix("LIMIT 20") + "LIMIT 10",
    "finance": fin_sql.removesuffix("LIMIT 20") + "LIMIT 5",
}
GT_PARAMETERS["R01"] = {
    "week": FILTERS["week"], "service": FILTERS["service"], "sales": SALES_FIXTURES["finance"],
}
CONTRACTS["R01"] = {
    "booking": {"columns": r_csm_columns, "precision": {"cancellation_pct": 2}},
    "finance": {"columns": r_fin_columns, "precision": {"total_outstanding": 6}},
}
assert source_markers() == SOURCE_MARKER, (
    "Sources changed while preparing shared answers. Rerun cells 3-5."
)
preparation_stamp("shared", ground_truth_payload())
print("Shared-source expected answers checked. Next: cell 6, question setup.")
print("Representatives are selected separately in each source; names are not linked across sources.")
print("These fields do not establish finance currency or upstream data freshness.")
```

## Cell 6 | Show the questions and reference answers

Show the exact questions, expected grains and reference SQL. Do not send reference answers to the tested agents.

```python
# Cell 6 | Show the questions and reference answers
# Keep the full prompt unchanged when asking either agent.

V2_BENCHMARK_READY = False
DRAFT_REVIEW_SHA256 = None
assert "PREPARATION_STAMPS" in globals(), "Run notebook cells 3-5 successfully first."
invalidate_preparation("questions")
assert "shared" in PREPARATION_STAMPS, "Notebook cell 5 has not completed successfully. Do not continue after an earlier cell failed."
require_preparation("shared", ground_truth_payload())
# The ranking fixtures need at least one usable value. Keep missing values in
# the answers; this check does not change their population or ordering.
assert any(row["total_outstanding"] is not None for row in GT["D01"]["answer"]), "Finance ranking has no populated balance. Review the fixture."
assert any(row["severity"] is not None for row in GT["D04"]["answer"]), "Case ranking has no populated severity. Review the fixture."
assert GT["D09"]["answer"][0]["created_ts"] is not None, "The selected Outlook has no creation time. Review the fixture."
# These inputs must match the fixed question wording.
assert FILTERS == {"week": "2026WK22", "service": "PVCS", "tcr": "HKG"}, "The question wording and configured filters differ. Review a new question version first."
assert MISSING_CUSTOMER == "CSM_POC_V2_NO_MATCH_20260901"
assert all(LOOKUP_FIXTURE[name] == FILTERS[key] for name, key in [("week_num", "week"), ("service", "service"), ("tcr", "tcr")])

QUESTIONS = {
    "C01": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations with the lowest confirmed utilization of their total reviewed commitment. Include confirmed TEU, total reviewed commitment and the utilization percentage. Only include combinations where the percentage can be calculated.",
    "C02": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as low booking. Include confirmed TEU, booked TEU and total reviewed commitment, with the lowest confirmed utilization first.",
    "C03": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as high cancellation. Include cancelled TEU, booked TEU and cancellation percentage, highest percentage first.",
    "C04": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as high rejection. Include rejected TEU, booked TEU and rejection percentage, highest percentage first.",
    "C05": "For week 2026WK22 and service PVCS, show the 20 customer, agreement and TCR combinations marked as above CSAL. Include booked TEU, confirmed TEU, total reviewed commitment and booking utilization, highest booking utilization first.",
    "C06": "Show the booking summary for customer {customer}, agreement {agreement}, week 2026WK22, service PVCS and TCR HKG. Include confirmed, cancelled, rejected, pended, terminated, no-show and total booked TEU. Return one summary, even if it appears against several allocation records.",
    "C07": "Show the booking summary for the exact customer name CSM_POC_V2_NO_MATCH_20260901, in week 2026WK22 and service PVCS. If there is no match, tell me. Do not substitute another customer.",
    "D01": "Using the latest snapshot in the finance source, show the 20 records with the largest outstanding balances for sales representative {sales}. Include customer, outstanding balance, oldest aging in days, recorded AR severity and snapshot date.",
    "D04": "Show the 10 cases with the highest recorded severity for sales representative {sales}. Include case ID, customer, state, severity, recommendation and the recorded data-as-of time.",
    "D06": "For sales representative {sales}, show up to 20 cases with no recorded issues. Include case ID, customer and state.",
    "D09": "For sales representative {sales}, show the most recently created Daily Outlook that is marked current. Include its ID, creation time and data-as-of time. Only retrieve the existing deliverable; do not create or send anything.",
    "R01": "Give me two separate lists: the 10 booking combinations marked as high cancellation with the highest cancellation percentages in week 2026WK22 and service PVCS, and the five finance records with the largest outstanding balances for sales representative {sales}, using the finance source's latest snapshot. Show the source and available data date for each list. Keep the lists separate; do not assume they describe the same customers.",
}
QUESTIONS["C06"] = QUESTIONS["C06"].format(**LOOKUP_FIXTURE)
for qid, domain in [("D01", "finance"), ("D04", "cases"), ("D06", "no_issues"), ("D09", "outlook"), ("R01", "finance")]:
    QUESTIONS[qid] = QUESTIONS[qid].format(sales=SALES_FIXTURES[domain])

# Both agents receive the same sorting, tie-breaking and display instructions.
METHOD_VERSION = "v2_first12_order_precision_1"
booking_ties_note = "For ties, sort customer, agreement, week_num, service and TCR ascending, with missing values last. Keep TEU exact and NULL separate from zero."
finance_ties_note = "Keep balances to six decimals and missing values last. Break ties by customer, sales, sales_full, snapshot_date, overdue_invoices, max_aging_days, ar_severity, overdue_30_amount, overdue_60_amount and overdue_90_amount, ascending."
METHOD_NOTES = {
    "C01": "Rank on unrounded confirmed utilization; show the percentage to six decimals. " + booking_ties_note,
    "C02": "Rank on unrounded confirmed utilization, with missing percentages last. Keep all stored low-booking matches eligible. " + booking_ties_note,
    "C03": "Use the cancellation percentage rounded to two decimals for ranking and display. " + booking_ties_note,
    "C04": "Use the rejection percentage rounded to two decimals for ranking and display. " + booking_ties_note,
    "C05": "Use the booking-utilization percentage rounded to two decimals for ranking and display. " + booking_ties_note,
    "C06": "Keep the TEU values exact and NULL separate from zero.",
    "C07": "",  # No extra projection is required for a genuine no-match answer.
    "D01": finance_ties_note,
    "D04": "Keep numeric severity to six decimals, with missing values last. Break ties by case ID ascending. Preserve the recorded timestamp precision.",
    "D06": "Sort case ID ascending. A case must have no issue records at all, not just no active issues.",
    "D09": "Break creation-time ties by deliverable ID ascending, with missing creation times last. Preserve the recorded timestamp precision.",
    "R01": "For the booking list, use cancellation percentages rounded to two decimals for ranking and display. " + booking_ties_note + " For the finance list: " + finance_ties_note,
}
PROMPTS = {qid: question + ("\n\n" + METHOD_NOTES[qid] if METHOD_NOTES[qid] else "") for qid, question in QUESTIONS.items()}
TRACEABILITY = {
    "C01": "question_bank.md 1; FR-002/FR-012; CSM column dictionary; confirmed utilization",
    "C02": "question_bank.md 2; FR-002/FR-012; stored low-booking signal",
    "C03": "question_bank.md 3; FR-003; stored high-cancellation signal",
    "C04": "question_bank.md 4; FR-003; stored high-rejection signal",
    "C05": "question_bank.md 5; FR-012; stored above-CSAL signal",
    "C06": "question_bank.md 6; CSM grain/column lineage; repeated booking measures",
    "C07": "question_bank.md 7; exact-filter and no-match guardrail",
    "D01": "question_bank.md 15; finance specification; fincon_issues dictionary",
    "D04": "question_bank.md 18; FR-007/FR-008; case ledger dictionary",
    "D06": "question_bank.md 20; data-quality requirements; ledger/issue case_id relationship",
    "D09": "question_bank.md 23; FR-014; TEA data contract; task_name runtime binding",
    "R01": "question_bank.md 27; supervisor routing; separate C03 and D01 answers",
}
assert set(GT) == set(CONTRACTS) == set(QUESTIONS) == set(QUESTION_IDS)
DRAFT_REVIEW_SHA256 = fingerprint(review_payload())
preparation_stamp("questions", review_payload())


def show_reference(qid):
    assert qid in QUESTION_IDS
    print(PROMPTS[qid])
    print("Requirement:", TRACEABILITY[qid])
    print("Expected grain:", "booking scope" if qid.startswith("C") else
          {"D01": "finance source record", "D04": "case_id", "D06": "case_id", "D09": "deliverable_id", "R01": "separate booking scopes and finance source records"}[qid])
    print("Reference rows and SQL (keep this output in the personal workspace):")
    for section, rows in GT[qid].items():
        print(section, stable_json(rows))
        print(GT_SQL[qid][section])


for qid in QUESTION_IDS:
    print(qid, {section: len(rows) for section, rows in GT[qid].items()}, "reference rows")
print("Use show_reference('C01') and the other question IDs to see each question, answer and SQL.")
print("Include the sorting and precision notes. Share PROMPTS for an identical team test.")
print("Reference fingerprint:", DRAFT_REVIEW_SHA256)
print("Next: cell 7 saves this exact setup.")
print("These are independently cross-checked reference calculations, not business-policy sign-off or agent results.")
```

## Cell 7 | Save the test setup

Save or resume this revision's personal evidence file. Earlier evidence files are not loaded or changed.

```python
# Cell 7 | Save the test setup
# Save one checkpoint in the personal workspace so the same test can resume.
# It can contain business rows and must stay in that workspace.

V2_BENCHMARK_READY = False


assert "PREPARATION_STAMPS" in globals() and "questions" in PREPARATION_STAMPS, "Notebook cells 3-6 must complete successfully before freezing."
require_preparation("sources", SOURCE_MARKER)
require_preparation("booking", booking_payload())
require_preparation("shared", ground_truth_payload())
require_preparation("questions", review_payload())
assert DRAFT_REVIEW_SHA256 == fingerprint(review_payload()), "Reference answers changed. Repeat cells 3-6 before saving."
assert spark.conf.get("spark.sql.session.timeZone") == SESSION_TIME_ZONE, "Session timezone changed. Recheck the timestamp results."
assert source_markers() == SOURCE_MARKER, "Source data changed since preparation. Keep existing evidence separate and prepare the reference answers again."

MANIFEST = {
    "label": EXPERIMENT_LABEL, "code_version": CODE_VERSION, "wording_version": WORDING_VERSION,
    "method_version": METHOD_VERSION, "sources": SOURCE_MARKER, "baseline_version": BASELINE_VERSION,
    "original_gold_version": 32, "endpoints": ENDPOINTS, "warehouse": WAREHOUSE_ID,
    "prompts": PROMPTS, "expected": GT, "ground_truth_sql": GT_SQL, "ground_truth_parameters": GT_PARAMETERS,
    "contracts": CONTRACTS, "traceability": TRACEABILITY, "fixtures": {"lookup": LOOKUP_FIXTURE, "sales": SALES_FIXTURES},
    "reference_sha256": DRAFT_REVIEW_SHA256, "repetitions": REPETITIONS,
    "reference_status": "CALCULATIONS_CROSS_CHECKED_NOT_BUSINESS_SIGNED_OFF",
    "session_timezone": SESSION_TIME_ZONE,
    "experiment_note": "New client revision. Earlier uncertain attempts remain in their original evidence files; they are not reconciled or erased by this run.",
    "limitations": ["Underlying managed models and equality are unverified.", "This is not a replica of the custom production supervisor.",
                    "Shared sources are live; version markers detect drift but do not lock the data.",
                    "The warehouse ID is the intended setting, not proof of actual per-request warehouse use.",
                    "Agent instructions and reader equality were inspected previously, not freshly verified by this notebook.",
                    "Agreement with reference SQL does not independently certify business policy.",
                    "Only 12 of the 41 proposed questions are in this batch.", "Enrichment, threshold calibration and swap scoring remain deferred."],
}
# Round-trip into JSON-safe values so resuming preserves the same fingerprint.
MANIFEST = json.loads(stable_json(MANIFEST))
EXPERIMENT_ID = fingerprint(MANIFEST)


def trial_id(qid, arm, repetition):
    return fingerprint([EXPERIMENT_ID, qid, arm, repetition])


PLAN = []
for repetition in range(1, REPETITIONS + 1):
    for number, qid in enumerate(QUESTION_IDS):
        # Alternate which arm goes first; keep each question/repetition paired.
        arms = ["A", "B"] if (number + repetition) % 2 else ["B", "A"]
        for arm in arms:
            PLAN.append({"trial_id": trial_id(qid, arm, repetition), "question": qid, "arm": arm, "repetition": repetition})
assert len(PLAN) == len({item["trial_id"] for item in PLAN}) == len(QUESTION_IDS) * len(ENDPOINTS) * REPETITIONS


def validate_evidence_path():
    expected_parent = Path("/Workspace/Users/" + PERSONAL_OWNER + "/Sales AI EDA")
    assert EVIDENCE_PATH.parent == expected_parent and EVIDENCE_PATH.name == "v2-benchmark-client-evidence.json"
    assert expected_parent.is_dir(), "Personal workspace files are unavailable. Stop; do not use another destination."
    assert not EVIDENCE_PATH.is_symlink(), "Unexpected evidence-file symlink."


def save_checkpoint(state):
    validate_evidence_path()
    payload = stable_json(state)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".v2-evidence-", dir=str(EVIDENCE_PATH.parent), delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(EVIDENCE_PATH))
        assert EVIDENCE_PATH.read_text(encoding="utf-8") == payload, "Evidence read-back failed. Stop before another request."
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


validate_evidence_path()
# Use the same lock for creation and resuming. Never replace an old experiment.
lock = EVIDENCE_PATH.with_suffix(".lock")
fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
try:
    if EVIDENCE_PATH.exists():
        STATE = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        assert STATE["experiment_id"] == EXPERIMENT_ID and STATE["manifest"] == MANIFEST, "An existing checkpoint has different test settings. Keep it unchanged; do not overwrite or delete it."
        assert STATE["plan"] == PLAN, "Saved trial plan differs."
        print("Existing experiment loaded. Completed or uncertain trials will not be resubmitted.")
    else:
        STATE = {"experiment_id": EXPERIMENT_ID, "manifest": MANIFEST, "plan": PLAN, "trials": {}, "created_at_utc": utc_now()}
        save_checkpoint(STATE)
        print("Personal evidence file created and read back.")
    V2_BENCHMARK_READY = True
finally:
    os.close(fd)
    lock.unlink()
print("Setup saved. Next: run cells 8-11. No agent question was sent.")
```

## Cell 8 | Check both agent connections

Prepare the supported client and read endpoint details. This does not send a benchmark question.

```python
# Cell 8 | Check both agent connections
# This reads endpoint details and prepares the client. No question is sent here.

AGENT_CLIENT = None
AGENT_CLIENT_SETTINGS = None
assert globals().get("DatabricksOpenAI") is not None, "Run cell 1 first. The databricks-openai package must be available."
CLIENT_PACKAGES = {name: package_version(name) for name in ("databricks-openai", "openai", "databricks-sdk")}
print("Client packages:", CLIENT_PACKAGES)
assert "follow_redirects" in inspect.signature(DatabricksOpenAI).parameters, (
    "This client needs databricks-openai 0.17 or later. Share the installed version before changing packages."
)
assert int(CLIENT_PACKAGES["openai"].split(".")[0]) < 3, "This Databricks integration requires OpenAI below version 3. No question was sent."
CLIENT = WorkspaceClient()


def as_dict(value):
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, str):
        return json.loads(value)
    assert isinstance(value, dict), "Connection metadata has an unexpected format."
    return value


def endpoint_identity(arm):
    info = as_dict(CLIENT.serving_endpoints.get(name=ENDPOINTS[arm]))
    assert info.get("state", {}).get("ready") == "READY", arm + ": endpoint is not Ready."
    assert not info.get("pending_config"), arm + ": endpoint has a pending configuration."
    config = info.get("config", {})
    entities = config.get("served_entities", config.get("served_models", []))
    fields = ("name", "entity_name", "entity_version", "model_name", "model_version", "workload_size", "scale_to_zero_enabled")
    return {"name": info.get("name"), "id": info.get("id"), "config_version": config.get("config_version"),
            "entities": [{key: item.get(key) for key in fields} for item in entities],
            "traffic_config": config.get("traffic_config")}


def validate_request_settings():
    assert isinstance(ENDPOINTS, dict) and set(ENDPOINTS) == {"A", "B"}, "Exactly endpoints A and B are required."
    assert isinstance(REQUEST_CONTRACT, dict) and REQUEST_CONTRACT == {"A": "input", "B": "input"}, "Both agents use the input request format."
    assert isinstance(HTTP_TIMEOUT_SECONDS, (int, float)) and not isinstance(HTTP_TIMEOUT_SECONDS, bool), "HTTP timeout must be a number."
    assert math.isfinite(HTTP_TIMEOUT_SECONDS) and HTTP_TIMEOUT_SECONDS > 0, "HTTP timeout must be finite and positive."


def request_client_settings():
    validate_request_settings()
    assert CLIENT.config.host.rstrip("/") + "/serving-endpoints" == AGENT_BASE_URL, "Workspace host changed. Stop this run."
    assert AGENT_CLIENT.timeout == HTTP_TIMEOUT_SECONDS, "Client timeout differs from the notebook setting."
    return {"base_url": str(AGENT_CLIENT.base_url).rstrip("/"), "timeout_seconds": AGENT_CLIENT.timeout,
            "max_retries": AGENT_CLIENT.max_retries,
            "packages": {name: package_version(name) for name in CLIENT_PACKAGES}}


def prepare_invocation(arm, prompt):
    assert V2_BENCHMARK_READY, "Run cell 7 before preparing an agent question."
    assert request_client_settings() == AGENT_CLIENT_SETTINGS, "Agent client settings changed. Stop this run."
    assert arm in {"A", "B"} and isinstance(prompt, str) and prompt.strip(), "Choose an assigned agent and a nonempty question."
    endpoint = ENDPOINTS[arm]
    assert endpoint == MANIFEST["endpoints"][arm], "Endpoint differs from the saved experiment."
    assert endpoint in {"mas-3beadca0-endpoint", "mas-6b7af80b-endpoint"}, "Only the two personal endpoints are allowed."
    return {"model": endpoint, "input": [{"role": "user", "content": prompt}], "stream": False}


def invoke_once(arm, prompt, prepared=None):
    payload = prepare_invocation(arm, prompt)
    assert prepared is None or prepared == payload, "Prepared request differs from this question."
    # Return the original HTTP response so the runner can save it before checking answers.
    return AGENT_CLIENT.responses.with_raw_response.create(**payload)


validate_request_settings()
assert ENDPOINTS == MANIFEST["endpoints"] == {"A": "mas-3beadca0-endpoint", "B": "mas-6b7af80b-endpoint"}, "Only the saved personal agent pair is allowed."
host = CLIENT.config.host.rstrip("/")
address = urlsplit(host)
assert (address.scheme == "https" and address.hostname and not address.username and not address.password
        and not address.path and not address.query and not address.fragment), "The workspace URL is not valid."
AGENT_BASE_URL = host + "/serving-endpoints"
AGENT_CLIENT = DatabricksOpenAI(workspace_client=CLIENT, base_url=AGENT_BASE_URL, use_ai_gateway=False,
                              follow_redirects=False, timeout=HTTP_TIMEOUT_SECONDS, max_retries=0)
assert callable(getattr(getattr(AGENT_CLIENT.responses, "with_raw_response", None), "create", None)), "The installed client does not support Responses."
AGENT_CLIENT_SETTINGS = request_client_settings()
assert AGENT_CLIENT_SETTINGS["base_url"] == AGENT_BASE_URL and AGENT_CLIENT_SETTINGS["max_retries"] == 0
assert AGENT_CLIENT_SETTINGS["timeout_seconds"] == HTTP_TIMEOUT_SECONDS
ENDPOINT_IDENTITIES = {arm: endpoint_identity(arm) for arm in ENDPOINTS}
print("Both connections are ready. Retries and redirects are disabled. No question was sent.")
print("Next: run cells 9, 10 and 11. Cell 12 sends the first A/B pair.")
```

## Cell 9 | Set up the paired runner

Load the paired runner. It saves each attempt before sending and preserves uncertain outcomes.

```python
# Cell 9 | Set up the paired runner
# Cell 12 calls this runner. Loading it does not send a question.


@contextmanager
def evidence_lock():
    validate_evidence_path()
    lock_path = EVIDENCE_PATH.with_suffix(".lock")
    # Only one runner can write at a time. Keep a leftover lock for investigation.
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink()


def load_checkpoint():
    assert fingerprint(MANIFEST) == EXPERIMENT_ID, "The in-memory frozen manifest was edited. Stop."
    loaded = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert loaded["experiment_id"] == EXPERIMENT_ID and loaded["manifest"] == MANIFEST
    assert loaded["plan"] == PLAN
    assert set(loaded["trials"]).issubset({item["trial_id"] for item in PLAN})
    return loaded


def current_transport():
    validate_request_settings()
    assert ENDPOINTS == MANIFEST["endpoints"], "Endpoint names differ from the saved test setup."
    assert WAREHOUSE_ID == MANIFEST["warehouse"]
    return {"identities": {arm: endpoint_identity(arm) for arm in ENDPOINTS},
            "request_contract": dict(REQUEST_CONTRACT), "timeout_seconds": HTTP_TIMEOUT_SECONDS,
            "client": request_client_settings(), "mode": "nonstreaming_fresh_request"}


def response_problem(response):
    """Recognize an unfinished reply without trying to continue it automatically."""
    if response.get("status") in {"incomplete", "failed", "cancelled", "queued", "in_progress"}:
        return "Agent response status: " + response["status"]
    if response.get("error") or response.get("incomplete_details"):
        return "Agent returned an error or incomplete-response details."
    for item in response.get("output") or []:
        if isinstance(item, dict) and item.get("type") in {"task_continue_request", "error"}:
            return "Agent returned a continuation request or error item."
    return None


def run_next_pairs(max_trials=2):
    global STATE
    assert V2_BENCHMARK_READY, "Run cells 1-7 successfully first."
    assert globals().get("V2_SCORING_SELF_TESTS_PASSED") is True, "Run the scoring self-tests first."
    assert isinstance(max_trials, int) and not isinstance(max_trials, bool) and 2 <= max_trials <= len(PLAN) and max_trials % 2 == 0
    require_preparation("questions", review_payload())
    assert MANIFEST["reference_sha256"] == fingerprint(review_payload()), "Reference answers no longer match the saved questions. Keep this test unchanged and prepare the new setup separately."
    submitted = 0
    with evidence_lock():
        STATE = load_checkpoint()
        transport = current_transport()
        if "transport" not in STATE:
            STATE["transport"] = transport
            save_checkpoint(STATE)
        assert STATE["transport"] == transport, "Endpoint/request settings changed. Preserve this experiment."
        uncertain = [row for row in STATE["trials"].values() if row["state"] in {"SUBMITTED", "UNKNOWN"}]
        assert not uncertain, "A prior request has uncertain completion. Reconcile its existing evidence; do not resubmit it."
        assert not any(row.get("response_problem") for row in STATE["trials"].values()), (
            "A saved reply is unfinished or contains an error. Inspect it before continuing."
        )
        pending_checks = [row for row in STATE["trials"].values() if row["state"] == "RECEIVED" and row.get("source_check") not in {"STABLE", "INCONCLUSIVE"}]
        assert not pending_checks, "A saved response is missing its post-run source checks. Resolve that record before continuing."
        if any(row.get("source_check") == "INCONCLUSIVE" for row in STATE["trials"].values()):
            raise RuntimeError("Source or endpoint checks changed or could not be verified. Keep the evidence and investigate before continuing.")
        selected = []
        remaining_budget = max_trials
        for position in range(0, len(PLAN), 2):
            pair = PLAN[position:position + 2]
            missing = [item for item in pair if item["trial_id"] not in STATE["trials"]]
            if not missing:
                continue
            if len(missing) > remaining_budget:
                break
            selected.extend(missing)
            remaining_budget -= len(missing)
        for item in selected:
            key = item["trial_id"]
            if key in STATE["trials"]:
                continue  # Includes completed, error and rejected submissions; never retry an answer.
            before = source_markers()
            assert before == MANIFEST["sources"], "Sources changed since ground truth. No new request was sent."
            assert current_transport() == STATE["transport"], "Endpoint configuration drift."
            prepared = prepare_invocation(item["arm"], MANIFEST["prompts"][item["question"]])
            row = dict(item, state="SUBMITTED", attempt=1, started_at_utc=utc_now(), source_before=before,
                       prompt_sha256=fingerprint(MANIFEST["prompts"][item["question"]]), request_payload_sha256=fingerprint(prepared),
                       submission_note="Saved before network submission; a crash now is uncertain, not retryable.")
            STATE["trials"][key] = row
            save_checkpoint(STATE)
            started = time.perf_counter()
            stage = "agent_request"
            try:
                reply = invoke_once(item["arm"], MANIFEST["prompts"][item["question"]], prepared=prepared)
                row["http_status"] = reply.status_code
                row["request_id"] = reply.headers.get("x-databricks-request-id") or reply.headers.get("x-request-id")
                stage = "read_response"
                response = reply.http_response.json()
                assert isinstance(response, dict), "Agent response is not a JSON object."
                row.update(response=response, response_fingerprint=fingerprint(response),
                           response_id=response.get("id"), response_status=response.get("status"),
                           response_problem=response_problem(response),
                           state="RECEIVED", completed_at_utc=utc_now(),
                           client_end_to_end_seconds=time.perf_counter() - started)
            except Exception as error:
                # Keep the failure useful without logging tokens, headers or request bodies.
                cause = error.__cause__ or error.__context__
                error_response = getattr(error, "response", None)
                error_headers = getattr(error_response, "headers", {})
                row.update(state="UNKNOWN", completed_at_utc=utc_now(),
                           error_type=type(error).__name__, error_stage=stage,
                           error_cause_type=type(cause).__name__ if cause else None,
                           failure_elapsed_seconds=time.perf_counter() - started,
                           http_status=getattr(error, "status_code", row.get("http_status")),
                           request_id=error_headers.get("x-databricks-request-id")
                           or getattr(error, "request_id", None) or row.get("request_id"))
                save_checkpoint(STATE)
                detail = {name: row.get(name) for name in (
                    "question", "arm", "error_stage", "error_type", "error_cause_type",
                    "http_status", "request_id", "failure_elapsed_seconds")}
                print("Request failed:", stable_json(detail))
                raise RuntimeError("Request completion is uncertain. Details saved above; no retry was made.") from None
            # Persist the response before making any further metadata call.
            row["source_check"] = "PENDING"
            save_checkpoint(STATE)
            try:
                after = source_markers()
                transport_after = current_transport()
                row["source_after"] = after
                row["transport_after"] = transport_after
                row["source_check"] = "STABLE" if before == after == MANIFEST["sources"] and transport_after == STATE["transport"] else "INCONCLUSIVE"
            except Exception as error:
                row["source_check"] = "INCONCLUSIVE"
                row["source_check_error"] = type(error).__name__
            save_checkpoint(STATE)
            submitted += 1
            print(item["question"], item["arm"], "repeat", item["repetition"], row["state"], row["source_check"])
            print("Agent response status:", row.get("response_status") or "not supplied")
            print("Response:", stable_json(row["response"]))
            print("Response time:", round(row["client_end_to_end_seconds"], 2), "seconds")
            assert row["source_check"] == "STABLE", "Source state changed or could not be verified. Pair is inconclusive."
            assert not row.get("response_problem"), (
                "The agent has not supplied a completed answer. Its response is saved; inspect it without resending."
            )
    print("New submissions:", submitted, "Recorded trials:", len(STATE["trials"]), "of", len(PLAN))


print("Paired runner loaded. No question was sent.")
print("Next: run cells 10 and 11 to load and test the answer comparisons.")
```

## Cell 10 | Compare recorded answers with the reference rows

Compare actual values with reference values, keeping NULL, zero and numeric precision separate.

```python
# Cell 10 | Compare recorded answers with the reference rows
# Loads comparison functions only. Next, run the synthetic checks in cell 11.
# Supply an alias only after verifying that both column names mean the same thing.

# Timestamps with a timezone are compared in UTC; those without one stay unchanged.
# Date strings stay strings. This rule does not infer source timezones.
V2_SCORING_DATETIME_RULE = "aware_utc_naive_unchanged"
V2_SCORING_SELF_TESTS_PASSED = False


def _v2_decimal(value):
    """Read a plain finite number without silently cleaning or changing it."""
    if isinstance(value, bool):
        raise ValueError("A Boolean is not a numeric measure.")
    if not isinstance(value, (int, float, Decimal, str)):
        raise ValueError("Unsupported numeric representation.")
    text = str(value)
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
        raise ValueError("Expected a plain number, without commas, percent signs or spaces.")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("The numeric value could not be read.") from exc
    if not number.is_finite():
        raise ValueError("NaN and infinity are not valid comparison values.")
    digits = number.as_tuple()
    if len(digits.digits) > 1000 or abs(digits.exponent) > 1000:
        raise ValueError("The numeric value is outside the scorer's supported size.")
    return number


def _v2_decimal_token(number, precision):
    """Create an exact token; fixed precision uses decimal half-up rounding."""
    parts = number.as_tuple()
    coefficient = int("".join(str(digit) for digit in parts.digits))
    exponent = parts.exponent
    if precision is not None:
        shift = exponent + precision
        if shift >= 0:
            coefficient *= 10 ** shift
        else:
            divisor = 10 ** (-shift)
            coefficient, remainder = divmod(coefficient, divisor)
            if remainder * 2 >= divisor:
                coefficient += 1
        exponent = -precision
    if coefficient == 0:
        return "0"
    while coefficient % 10 == 0:
        coefficient //= 10
        exponent += 1
    sign = "-" if parts.sign else ""
    return f"{sign}{coefficient}e{exponent}"


def _v2_value_token(value, is_numeric, precision):
    if value is None:
        return ["null"]
    if is_numeric:
        return ["number", _v2_decimal_token(_v2_decimal(value), precision)]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, datetime):
        if V2_SCORING_DATETIME_RULE != "aware_utc_naive_unchanged":
            raise ValueError("The datetime serialization rule is not recognized.")
        if value.utcoffset() is not None:
            return ["datetime_utc", value.astimezone(timezone.utc).isoformat()]
        return ["datetime_naive", value.isoformat()]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    if isinstance(value, str):
        return ["text", value]
    if isinstance(value, (int, float, Decimal)):
        return ["number", _v2_decimal_token(_v2_decimal(value), None)]
    raise ValueError("An output value has an unsupported type.")


def _v2_row_tokens(rows, columns, numeric_precision, names):
    tokens = []
    for row_number, row in enumerate(rows, 1):
        values = []
        for column in columns:
            try:
                values.append(_v2_value_token(
                    row[names[column]], column in numeric_precision,
                    numeric_precision.get(column),
                ))
            except (ValueError, TypeError, OverflowError) as exc:
                # Do not include customer values in diagnostics.
                raise ValueError(
                    f"Row {row_number}, column {column}: {exc}"
                ) from exc
        tokens.append(json.dumps(values, ensure_ascii=False, separators=(",", ":")))
    return tokens


def _v2_tokens_hash(tokens, ordered):
    canonical = tokens if ordered else sorted(tokens)
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def score_section(expected_rows, actual_rows, columns, numeric_precision, aliases, ordered=True):
    """Compare structured rows, not prose, with the selected reference columns.

    numeric_precision maps numeric columns to decimal places, or None for exact
    values. Unlisted columns retain their types. aliases maps canonical names to
    actual response names. Supplying an alias confirms its meaning was checked.

    Correct business values can pass even when naming or extra columns violate
    the output contract. An empty answer requires separate retrieval evidence;
    this function cannot prove that an empty list came from a real query.
    """
    result = {
        "status": "NOT_EVALUABLE",
        "reasons": [],
        "hashes": {"expected": None, "actual": None},
        "expected_hash": None,
        "actual_hash": None,
        "contract_compliant": None,
        "contract_reasons": [],
        "expected_row_count": len(expected_rows) if isinstance(expected_rows, list) else None,
        "actual_row_count": len(actual_rows) if isinstance(actual_rows, list) else None,
    }

    def stop(status, reason):
        result["status"] = status
        result["reasons"].append(reason)
        return result

    if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
        return stop("NOT_EVALUABLE", "Both evidence inputs must be lists of structured rows.")
    if not isinstance(columns, list) or not columns or any(
        not isinstance(column, str) or not column for column in columns
    ) or len(set(columns)) != len(columns):
        return stop("NOT_EVALUABLE", "The reference projection must contain unique column names.")
    if not isinstance(numeric_precision, dict) or not isinstance(aliases, dict):
        return stop("NOT_EVALUABLE", "Precision and verified alias rules must be dictionaries.")
    if not isinstance(ordered, bool):
        return stop("NOT_EVALUABLE", "The ordering rule must be explicitly True or False.")
    if any(column not in columns for column in numeric_precision):
        return stop("NOT_EVALUABLE", "A precision rule names a column outside the projection.")
    if any(
        precision is not None and (
            isinstance(precision, bool) or not isinstance(precision, int)
            or not 0 <= precision <= 38
        )
        for precision in numeric_precision.values()
    ):
        return stop("NOT_EVALUABLE", "Numeric precision must be None or an integer from 0 to 38.")
    if any(
        column not in columns or not isinstance(name, str) or not name
        for column, name in aliases.items()
    ):
        return stop("NOT_EVALUABLE", "An alias rule is invalid or outside the projection.")
    actual_names = {column: aliases.get(column, column) for column in columns}
    if len(set(actual_names.values())) != len(actual_names):
        return stop("NOT_EVALUABLE", "Two reference columns map to the same answer column.")
    if any(not isinstance(row, dict) for row in expected_rows):
        return stop("NOT_EVALUABLE", "A reference row is not a dictionary.")
    if any(not isinstance(row, dict) for row in actual_rows):
        return stop("NOT_EVALUABLE", "An answer row is not a dictionary. Check the values copied from the saved response.")
    if any(any(column not in row for column in columns) for row in expected_rows):
        return stop("NOT_EVALUABLE", "The reference evidence is missing a required column.")

    expected_names = {column: column for column in columns}
    try:
        expected_tokens = _v2_row_tokens(expected_rows, columns, numeric_precision, expected_names)
    except ValueError as exc:
        return stop("NOT_EVALUABLE", f"Invalid reference evidence. {exc}")
    result["expected_hash"] = _v2_tokens_hash(expected_tokens, ordered)
    result["hashes"]["expected"] = result["expected_hash"]

    if actual_rows:
        expected_column_set = set(columns)
        result["contract_compliant"] = all(
            set(row) == expected_column_set for row in actual_rows
        ) and all(actual_names[column] == column for column in columns)
        if not result["contract_compliant"]:
            result["contract_reasons"].append(
                "Answer names or extra/missing columns differ from the requested projection."
            )
    else:
        result["contract_reasons"].append("An empty row list does not provide column-schema evidence.")
    if any(any(name not in row for name in actual_names.values()) for row in actual_rows):
        return stop("INCORRECT", "The recorded answer is missing a required business column.")
    try:
        actual_tokens = _v2_row_tokens(actual_rows, columns, numeric_precision, actual_names)
    except ValueError as exc:
        return stop("INCORRECT", f"Invalid answer value. {exc}")
    result["actual_hash"] = _v2_tokens_hash(actual_tokens, ordered)
    result["hashes"]["actual"] = result["actual_hash"]

    if len(expected_tokens) != len(actual_tokens):
        return stop("INCORRECT", "The answer row count differs from the reference.")
    matches = expected_tokens == actual_tokens if ordered else Counter(expected_tokens) == Counter(actual_tokens)
    if not matches:
        if ordered and Counter(expected_tokens) == Counter(actual_tokens):
            return stop("INCORRECT", "The values match, but the requested row order does not.")
        return stop("INCORRECT", "The requested business values or row membership differ.")
    return stop("CORRECT", "The requested rows and values match the reference under the declared rules.")


print("Scoring helpers loaded. Run cell 11 to test them with synthetic data.")
```

## Cell 11 | Test the scorer with synthetic records

Run the synthetic scorer checks. Passing these checks does not mean the agents passed the benchmark.

```python
# Cell 11 | Test the scorer with synthetic records
# Checks numbers, NULLs, row order, aliases and missing evidence. No source data.

V2_SCORING_SELF_TESTS_PASSED = False
_v2_test_count = 0


def _v2_expect(label, expected_status, expected_rows, actual_rows,
               columns=None, numeric_precision=None, aliases=None, ordered=True):
    global _v2_test_count
    outcome = score_section(
        expected_rows, actual_rows,
        ["id", "value"] if columns is None else columns,
        {"value": None} if numeric_precision is None else numeric_precision,
        {} if aliases is None else aliases,
        ordered=ordered,
    )
    assert outcome["status"] == expected_status, f"{label}: {outcome}"
    _v2_test_count += 1
    return outcome


_v2_base = [{"id": "synthetic", "value": Decimal("12.00")}]
# Numbers: exact comparison, declared rounding, invalid values and NULLs.
_v2_expect("Exact numeric representations", "CORRECT", _v2_base,
           [{"id": "synthetic", "value": "12"}])
_v2_expect("Exact TEU retains fractional differences", "INCORRECT", _v2_base,
           [{"id": "synthetic", "value": "12.000001"}])
_v2_expect("Half-up rounding", "CORRECT",
           [{"id": "synthetic", "value": "1.235"}],
           [{"id": "synthetic", "value": "1.24"}], numeric_precision={"value": 2})
_v2_expect("Negative half-up rounding", "CORRECT",
           [{"id": "synthetic", "value": "-1.235"}],
           [{"id": "synthetic", "value": "-1.24"}], numeric_precision={"value": 2})
_v2_expect("Six-place comparison", "CORRECT",
           [{"id": "synthetic", "value": "1.1234565"}],
           [{"id": "synthetic", "value": "1.123457"}], numeric_precision={"value": 6})
_v2_expect("Six-place difference remains visible", "INCORRECT",
           [{"id": "synthetic", "value": "1.123456"}],
           [{"id": "synthetic", "value": "1.123457"}], numeric_precision={"value": 6})
_v2_expect("Large decimal is not rounded by Python context", "INCORRECT",
           [{"id": "synthetic", "value": "12345678901234567890123456789012345678"}],
           [{"id": "synthetic", "value": "12345678901234567890123456789012345679"}])
_v2_expect("NULL remains different from zero", "INCORRECT",
           [{"id": "synthetic", "value": None}], [{"id": "synthetic", "value": 0}])
_v2_expect("Matching NULL values", "CORRECT",
           [{"id": "synthetic", "value": None}], [{"id": "synthetic", "value": None}])
_v2_expect("Signed zero", "CORRECT",
           [{"id": "synthetic", "value": "-0.00"}], [{"id": "synthetic", "value": 0}])

_v2_two_rows = [{"id": "first", "value": 1}, {"id": "second", "value": 2}]
# Rows: ordering and duplicate counts are separate requirements.
_v2_expect("Required order", "INCORRECT", _v2_two_rows, list(reversed(_v2_two_rows)))
_v2_expect("Unordered multiset", "CORRECT", _v2_two_rows, list(reversed(_v2_two_rows)), ordered=False)
_v2_expect("Expected repeated rows are legitimate", "CORRECT", _v2_base * 2, _v2_base * 2)
_v2_expect("Extra repeated row is not legitimate", "INCORRECT", _v2_base, _v2_base * 2)
_v2_expect("Multiset preserves duplicate counts", "INCORRECT",
           [_v2_two_rows[0], _v2_two_rows[0], _v2_two_rows[1]],
           [_v2_two_rows[0], _v2_two_rows[1], _v2_two_rows[1]], ordered=False)

# Columns: verified aliases can match values without matching the output contract.
_v2_alias_result = _v2_expect("Verified alias", "CORRECT", _v2_base,
                            [{"id": "synthetic", "amount": 12}], aliases={"value": "amount"})
assert _v2_alias_result["contract_compliant"] is False
_v2_extra_result = _v2_expect("Extra metadata does not change business correctness", "CORRECT", _v2_base,
                            [{"id": "synthetic", "value": 12, "metadata": "extra"}])
assert _v2_extra_result["contract_compliant"] is False
_v2_exact_result = _v2_expect("Exact contract", "CORRECT", _v2_base, _v2_base)
assert _v2_exact_result["contract_compliant"] is True
assert _v2_exact_result["expected_hash"] == _v2_exact_result["actual_hash"]
_v2_expect("Unmapped alias is not inferred", "INCORRECT", _v2_base,
           [{"id": "synthetic", "amount": 12}])
_v2_expect("Ambiguous alias mapping", "NOT_EVALUABLE", _v2_base, _v2_base,
           aliases={"id": "value"})
_v2_expect("Duplicate requested column", "NOT_EVALUABLE", _v2_base, _v2_base,
           columns=["id", "value", "value"])
_v2_expect("Missing ground-truth projection", "NOT_EVALUABLE",
           [{"id": "synthetic"}], _v2_base)
_v2_expect("Missing answer projection", "INCORRECT", _v2_base, [{"id": "synthetic"}])

# Invalid values remain errors; date and timestamp types are not guessed.
for _v2_bad_numeric in (True, "NaN", float("nan"), "Infinity", float("inf"), "1,000", "12%", " 12 "):
    _v2_expect("Reject invalid numeric answer", "INCORRECT", _v2_base,
               [{"id": "synthetic", "value": _v2_bad_numeric}])
_v2_expect("Reject invalid reference number", "NOT_EVALUABLE",
           [{"id": "synthetic", "value": float("nan")}], _v2_base)
_v2_expect("No hidden string-to-date coercion", "INCORRECT",
           [{"id": "synthetic", "value": date(2026, 1, 1)}],
           [{"id": "synthetic", "value": "2026-01-01"}], numeric_precision={})
_v2_expect("Aware timestamps use declared UTC rule", "CORRECT",
           [{"id": "synthetic", "value": datetime.fromisoformat("2026-01-01T08:00:00+08:00")}],
           [{"id": "synthetic", "value": datetime.fromisoformat("2026-01-01T00:00:00+00:00")}],
           numeric_precision={})
_v2_expect("Naive timestamp is not silently assigned UTC", "INCORRECT",
           [{"id": "synthetic", "value": datetime(2026, 1, 1)}],
           [{"id": "synthetic", "value": datetime(2026, 1, 1, tzinfo=timezone.utc)}],
           numeric_precision={})
_v2_empty_result = _v2_expect("Two empty result lists", "CORRECT", [], [])
assert _v2_empty_result["contract_compliant"] is None
_v2_expect("Unexpected nonempty answer", "INCORRECT", [], _v2_base)
_v2_expect("Missing actual evidence is not an empty answer", "NOT_EVALUABLE", [], None)
_v2_expect("Answer prose is not structured evidence", "NOT_EVALUABLE", _v2_base, ["No results"])
_v2_expect("Invalid precision", "NOT_EVALUABLE", _v2_base, _v2_base, numeric_precision={"value": True})

V2_SCORING_SELF_TESTS_PASSED = True
print(f"Scorer checks passed: {_v2_test_count} (synthetic data only).")
print("Next: manually run cell 12 once to ask the first question through both agents.")
```

## Cell 12 | Ask both agents

Run this cell once to send the next A/B pair. Read its result before running it again.

```python
# Cell 12 | Ask both agents
# Running this cell sends the next pair and saves both responses.
# Start with one pair. Read its results before running this cell again.

assert callable(globals().get("run_next_pairs")), "Run cells 7-11 first."
run_next_pairs(MAX_TRIALS_THIS_RUN)
print("Next: use cell 13 to compare the actual answers, then cell 14 for the report.")
```

## Cell 13 | Record the actual answers

Run this block to load the answer-recording helpers. Then use `show_trial('C01', 'A', 1)` to read the saved answer. Put its real row values in `actual_rows` and call `record_answer('C01', 'A', 1, actual_rows, note='Copied from the saved C01 A response')`. Repeat for B. This cell does not invent or automatically extract rows from prose. Optional SQL/source/grain checks stay unknown until supported by the original query or trace.

```python
# Cell 13 | Record the actual answers
# Copy rows from the saved agent response. Never copy the expected answers here.


def show_trial(question, arm, repetition=1):
    """Read one saved response without asking the agent again."""
    state = load_checkpoint()
    key = trial_id(question, arm, repetition)
    assert key in state["trials"], "This question has not been sent in this experiment."
    trial = state["trials"][key]
    print(f"{question} | Agent {arm} | Repetition {repetition}")
    print("State:", trial["state"], "| Source check:", trial.get("source_check"))
    print("Agent response status:", trial.get("response_status") or "not supplied")
    print(stable_json(trial.get("response")))
    return key


def record_answer(question, arm, repetition, rows, *, note,
                  narrative_correct=None, honest_no_match=None,
                  sources_and_dates_correct=None, sql=None,
                  source_isolation="NOT_EVALUABLE", grain_correctness="NOT_EVALUABLE",
                  answer_support="SUPPORTED", aliases=None, alias_note="",
                  sql_capture_complete=None, sql_capture_note=""):
    """Save copied rows and optional evidence. Unknown checks stay unknown.

    For most questions rows is a list of dictionaries. R01 has two lists:
    {"booking": booking_rows, "finance": finance_rows}.
    sql can be original SQL text or a list of SQL evidence dictionaries.
    """
    assert V2_BENCHMARK_READY, "Load this experiment before recording answers."
    assert question in QUESTION_IDS and arm in ENDPOINTS
    assert type(repetition) is int and 1 <= repetition <= REPETITIONS
    assert isinstance(note, str) and note.strip(), "Identify the original response used."
    assert answer_support in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"}
    for value in (narrative_correct, honest_no_match, sources_and_dates_correct, sql_capture_complete):
        assert value is None or type(value) is bool, "Use True, False or None for an unchecked claim."
    for value in (source_isolation, grain_correctness):
        assert value in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}

    sections = {"answer": rows} if isinstance(rows, list) else rows
    section_names = set(MANIFEST["contracts"][question])
    assert isinstance(sections, dict) and set(sections) == section_names
    assert all(isinstance(values, list) and all(isinstance(row, dict) for row in values)
               for values in sections.values()), "Use [] only for an actual empty result."
    aliases = {name: {} for name in section_names} if aliases is None else aliases
    assert set(aliases) == section_names and all(isinstance(value, dict) for value in aliases.values())
    assert not any(aliases.values()) or alias_note.strip(), "Explain how the SQL/source meaning verifies each alias."

    if isinstance(sql, str):
        assert sql.strip(), "Supply original SQL text or leave sql as None."
        sql = [{"text": sql, "evidence_note": note,
                "correctness": "NOT_EVALUABLE", "execution_seconds": None}]
    sql_evidence = [] if sql is None else sql
    assert isinstance(sql_evidence, list)
    for entry in sql_evidence:
        assert isinstance(entry, dict) and entry.get("text", "").strip()
        assert entry.get("evidence_note", "").strip(), "Identify the saved query or trace."
        assert entry.get("correctness") in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}
        seconds = entry.get("execution_seconds")
        assert seconds is None or (type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0)
        assert seconds is None or entry.get("timing_evidence", "").strip(), "SQL timing needs query-history evidence."
    assert sql_capture_complete is not True or (sql_evidence and sql_capture_note.strip()), (
        "A complete SQL capture needs its original statements and a note identifying the full trace."
    )

    with evidence_lock():
        state = load_checkpoint()
        key = trial_id(question, arm, repetition)
        trial = state["trials"].get(key)
        assert trial and trial["state"] == "RECEIVED", "No complete response was saved."
        assert trial["response_fingerprint"] == fingerprint(trial["response"]), "Saved response changed."
        assert not trial.get("response_problem"), "This reply is unfinished or contains an error."
        review = {
            "trial_key": key, "response_fingerprint": trial["response_fingerprint"],
            "reviewer": PERSONAL_OWNER, "evidence_note": note, "sections": sections,
            "aliases": aliases, "alias_evidence": alias_note, "answer_support": answer_support,
            "narrative_correct": narrative_correct, "honest_no_match": honest_no_match,
            "sources_and_dates_correct": sources_and_dates_correct,
            "source_isolation": source_isolation, "grain_correctness": grain_correctness,
            "sql_evidence": sql_evidence, "sql_capture_complete": sql_capture_complete,
            "sql_capture_note": sql_capture_note,
        }
        review = json.loads(stable_json(review))
        history = trial.setdefault("reviews", [])
        if not history or history[-1]["review"] != review:
            history.append({"at_utc": utc_now(), "review": review})
            save_checkpoint(state)
    print(f"Saved answer evidence: {question} | Agent {arm} | Repetition {repetition}.")
    return key


print("Read show_trial('C01', 'A', 1), then place its actual row values in actual_rows.")
print("record_answer('C01', 'A', 1, actual_rows, note='Copied from the saved C01 A response')")
print("Repeat for Agent B. Set narrative_correct=True only after checking the answer's claims.")
print("Missing SQL, source and grain checks remain unavailable. Cell 14 shows the comparison.")
```

## Cell 14 | Show the A/B results from saved answers

Show the comparison from saved evidence. It does not send another question.

```python
# Cell 14 | Show the A/B results from saved answers
# Recalculates and saves the report only; it does not send questions.


def sql_counts(text):
    # These are text heuristics, not a SQL parser or a SQL correctness check.
    cleaned = re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", " ", text, flags=re.S)
    calls = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", cleaned)
    keywords = {"select", "as", "in", "over", "with", "exists", "values", "using", "partition"}
    return {"characters": len(text), "lines": len(text.splitlines()),
            "join_tokens": len(re.findall(r"\bJOIN\b", cleaned, flags=re.I)),
            "cte_candidates": len(re.findall(r"\bAS\s*\(\s*SELECT\b", cleaned, flags=re.I)),
            "function_like_tokens": sum(name.lower() not in keywords for name in calls)}


def score_trial(trial, reference):
    """Combine the row comparison with the recorded answer and source checks."""
    if trial is None:
        return {"status": "PENDING", "row_correctness": "NOT_EVALUABLE", "reason": "Not submitted."}
    if trial.get("response_problem"):
        return {"status": "NOT_EVALUABLE", "row_correctness": "NOT_EVALUABLE", "reason": trial["response_problem"]}
    if trial["state"] != "RECEIVED" or not trial.get("reviews"):
        status = "NOT_EVALUABLE" if trial.get("source_check") == "STABLE" else "INCONCLUSIVE"
        return {"status": status, "row_correctness": "NOT_EVALUABLE", "reason": "Check and record the original response in cell 13 first."}
    review = trial["reviews"][-1]["review"]
    assert review["response_fingerprint"] == trial["response_fingerprint"] == fingerprint(trial["response"])
    question = trial["question"]
    scores = {}
    for section, contract in reference["contracts"][question].items():
        scores[section] = score_section(reference["expected"][question][section], review["sections"][section],
                                        contract["columns"], contract["precision"], review["aliases"][section], ordered=True)
    numeric_status = [result["status"] for result in scores.values()]
    row_correctness = ("NOT_EVALUABLE" if "NOT_EVALUABLE" in numeric_status else
                       "INCORRECT" if "INCORRECT" in numeric_status else "CORRECT")
    if review["answer_support"] != "SUPPORTED":
        status = review["answer_support"]  # Never counted as a correct supported answer.
    elif row_correctness == "INCORRECT" or review.get("narrative_correct") is False:
        status = "INCORRECT"
    elif question == "C07" and review.get("honest_no_match") is False:
        status = "INCORRECT"
    elif question == "R01" and review.get("sources_and_dates_correct") is False:
        status = "INCORRECT"
    elif row_correctness != "CORRECT" or review.get("narrative_correct") is not True:
        status = "NOT_EVALUABLE"
    elif question == "C07" and review.get("honest_no_match") is not True:
        status = "NOT_EVALUABLE"
    elif question == "R01" and review.get("sources_and_dates_correct") is not True:
        status = "NOT_EVALUABLE"
    else:
        status = "CORRECT"
    signature = None
    if all(result.get("actual_hash") for result in scores.values()):
        signature = fingerprint({section: result["actual_hash"] for section, result in scores.items()})
    sql_evidence = review["sql_evidence"]
    business_status = status
    if trial.get("source_check") != "STABLE" or review["source_isolation"] == "INCORRECT":
        status = "INCONCLUSIVE"  # Correct numbers from an unassigned source are not valid architecture evidence.
    return {"status": status, "business_status": business_status, "row_correctness": row_correctness,
            "sections": scores, "answer_signature": signature,
            "grain_correctness": review["grain_correctness"], "source_isolation": review["source_isolation"],
            "sql_correctness": [entry["correctness"] for entry in sql_evidence] or ["NOT_EVALUABLE"],
            "captured_sql_statement_count": len(sql_evidence),
            "sql_capture_complete": review.get("sql_capture_complete") is True,
            "sql_review_complete": bool(sql_evidence) and review.get("sql_capture_complete") is True
                                   and all(entry["correctness"] in {"CORRECT", "INCORRECT"} for entry in sql_evidence),
            "sql_complexity_heuristics": [sql_counts(entry["text"]) for entry in sql_evidence],
            "sql_execution_seconds": [entry.get("execution_seconds") for entry in sql_evidence]}


def build_report(state):
    """Summarize both agents while keeping missing and inconclusive evidence visible."""
    def valid_seconds(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

    scores = {item["trial_id"]: score_trial(state["trials"].get(item["trial_id"]), state["manifest"]) for item in state["plan"]}
    # If either arm drifted, its paired architecture comparison is also inconclusive.
    bad_pairs = {(item["question"], item["repetition"]) for item in state["plan"] if scores[item["trial_id"]]["status"] == "INCONCLUSIVE"}
    for item in state["plan"]:
        if (item["question"], item["repetition"]) in bad_pairs and item["trial_id"] in state["trials"]:
            scores[item["trial_id"]]["status"] = "INCONCLUSIVE"
    arms = {}
    for arm in ["A", "B"]:
        items = [item for item in state["plan"] if item["arm"] == arm]
        comparison_items = [item for item in items if scores[item["trial_id"]]["status"] not in {"PENDING", "INCONCLUSIVE"}]
        excluded_items = [item for item in items if scores[item["trial_id"]]["status"] == "INCONCLUSIVE"]
        counts = Counter(scores[item["trial_id"]]["status"] for item in items)
        latencies = [state["trials"][item["trial_id"]].get("client_end_to_end_seconds") for item in comparison_items
                     if state["trials"].get(item["trial_id"], {}).get("state") == "RECEIVED"]
        latencies = [value for value in latencies if valid_seconds(value)]
        evaluated = sum(counts[key] for key in ["CORRECT", "INCORRECT", "PARTIALLY_SUPPORTED", "UNSUPPORTED"])
        row_counts = Counter(scores[item["trial_id"]].get("row_correctness", "NOT_EVALUABLE") for item in comparison_items)
        captured_sql = [entry for item in comparison_items for entry in scores[item["trial_id"]].get("sql_complexity_heuristics", [])]
        sql_metrics = {name: statistics.median([entry[name] for entry in captured_sql]) if captured_sql else None
                       for name in ["characters", "lines", "join_tokens", "cte_candidates", "function_like_tokens"]}
        sql_seconds = [seconds for item in comparison_items for seconds in scores[item["trial_id"]].get("sql_execution_seconds", []) if valid_seconds(seconds)]
        sql_verdicts = Counter(verdict for item in comparison_items for verdict in scores[item["trial_id"]].get("sql_correctness", [])
                               if scores[item["trial_id"]].get("captured_sql_statement_count", 0) > 0)
        grain_verdicts = Counter(scores[item["trial_id"]].get("grain_correctness", "NOT_EVALUABLE") for item in comparison_items)
        isolation_verdicts = Counter(scores[item["trial_id"]].get("source_isolation", "NOT_EVALUABLE") for item in items)
        states = Counter(state["trials"][item["trial_id"]]["state"] if item["trial_id"] in state["trials"] else "NOT_SUBMITTED" for item in items)
        # Retain excluded evidence for audit, without mixing it into the comparison.
        audit_sql = [entry for item in items for entry in scores[item["trial_id"]].get("sql_complexity_heuristics", [])]
        audit_sql_verdicts = Counter(verdict for item in items for verdict in scores[item["trial_id"]].get("sql_correctness", [])
                                     if scores[item["trial_id"]].get("captured_sql_statement_count", 0) > 0)
        audit_grain_verdicts = Counter(scores[item["trial_id"]].get("grain_correctness", "NOT_EVALUABLE") for item in items)
        consistency = {}
        for question in QUESTION_IDS:
            group = [scores[trial_id(question, arm, repetition)] for repetition in [1, 2, 3]]
            hashes = [row.get("answer_signature") for row in group]
            if any(row["status"] in {"PENDING", "INCONCLUSIVE", "NOT_EVALUABLE"} for row in group) or any(value is None for value in hashes):
                consistency[question] = "NOT_EVALUABLE"
            else:
                consistency[question] = "STABLE" if len(set(hashes)) == 1 else "UNSTABLE"
        arms[arm] = {"planned": len(items), "status_counts": dict(counts), "evaluated": evaluated,
                     "correctness_pct_of_evaluated": round(100 * counts["CORRECT"] / evaluated, 1) if evaluated else None,
                     "row_correctness_counts": dict(row_counts),
                     "rows_evaluated": row_counts["CORRECT"] + row_counts["INCORRECT"],
                     "median_client_end_to_end_seconds": statistics.median(latencies) if latencies else None,
                     "timed_trials": len(latencies), "consistency": consistency,
                     "submission_states": dict(states), "grain_verdicts": dict(grain_verdicts), "sql_verdicts": dict(sql_verdicts),
                     "source_isolation_verdicts": dict(isolation_verdicts),
                     "captured_sql_statements": len(captured_sql), "median_sql_text_heuristics": sql_metrics,
                     "timed_sql_statements": len(sql_seconds),
                     "trials_with_complete_sql_review": sum(scores[item["trial_id"]].get("sql_review_complete") is True for item in comparison_items),
                     "trials_without_captured_sql": sum(scores[item["trial_id"]].get("captured_sql_statement_count", 0) == 0 for item in comparison_items),
                     "median_sql_execution_seconds": statistics.median(sql_seconds) if sql_seconds else None,
                     "audit_all_captured_sql_statements": len(audit_sql), "audit_all_sql_verdicts": dict(audit_sql_verdicts),
                     "audit_all_grain_verdicts": dict(audit_grain_verdicts), "excluded_inconclusive_trials": len(excluded_items),
                     "excluded_captured_sql_statements": sum(scores[item["trial_id"]].get("captured_sql_statement_count", 0) for item in excluded_items)}
    paired_deltas = []
    for question in QUESTION_IDS:
        for repetition in [1, 2, 3]:
            keys = [trial_id(question, arm, repetition) for arm in ["A", "B"]]
            trials = [state["trials"].get(key) for key in keys]
            if all(scores[key]["status"] not in {"PENDING", "INCONCLUSIVE"} for key in keys) and all(trial and trial.get("state") == "RECEIVED" and trial.get("source_check") == "STABLE" and valid_seconds(trial.get("client_end_to_end_seconds")) for trial in trials):
                paired_deltas.append(trials[1]["client_end_to_end_seconds"] - trials[0]["client_end_to_end_seconds"])
    answers_reviewed = all(scores[item["trial_id"]]["status"] in {"CORRECT", "INCORRECT", "PARTIALLY_SUPPORTED", "UNSUPPORTED"} for item in state["plan"])
    isolation_verified = all(scores[item["trial_id"]].get("source_isolation") == "CORRECT" for item in state["plan"])
    grain_reviewed = all(scores[item["trial_id"]].get("grain_correctness") in {"CORRECT", "INCORRECT"} for item in state["plan"])
    sql_reviewed = all(scores[item["trial_id"]].get("sql_review_complete") is True for item in state["plan"])
    answer_handoff_ready = answers_reviewed and isolation_verified
    handoff_ready = answer_handoff_ready and grain_reviewed and sql_reviewed
    client_timing_complete = sum(arm["timed_trials"] for arm in arms.values()) == len(state["plan"])
    sql_timing_complete = sql_reviewed and all(
        len(scores[item["trial_id"]].get("sql_execution_seconds", [])) == scores[item["trial_id"]].get("captured_sql_statement_count", 0)
        and all(valid_seconds(value) for value in scores[item["trial_id"]].get("sql_execution_seconds", []))
        for item in state["plan"])
    return {"experiment_id": state["experiment_id"], "generated_at_utc": utc_now(), "arms": arms,
            "question_scope": {"full_target": 41, "prepared_in_this_batch": len(QUESTION_IDS),
                               "remaining_pending": max(0, 41 - len(QUESTION_IDS))},
            "trial_scores": scores, "first12_evidence_complete": handoff_ready,
            "first12_answers_reviewed": answers_reviewed, "assigned_sources_verified_for_all_trials": isolation_verified,
            "first12_answer_review_handoff_ready": answer_handoff_ready,
            "first12_grain_review_complete": grain_reviewed, "first12_sql_review_complete": sql_reviewed,
            "client_response_timing_complete": client_timing_complete, "sql_execution_timing_complete": sql_timing_complete,
            "complete_timed_pairs": len(paired_deltas), "complete_timed_response_pairs": len(paired_deltas),
            "median_paired_B_minus_A_seconds": statistics.median(paired_deltas) if paired_deltas else None,
            "limitations": state["manifest"]["limitations"],
            "timing_note": "Client nonstreaming response latency, not SQL duration or exact UI latency. Timed pairs need not have correct or reviewed answers. Source checks are outside the timer. SQL timing availability is reported separately.",
            "evidence_note": "Complete review evidence requires reviewed answers, verified assigned sources, a resolved grain verdict and complete reviewed SQL capture for every trial. Incorrect findings still count as reviewed evidence. Missing platform timing remains explicitly unavailable and does not imply zero latency.",
            "sql_metrics_note": "SQL metrics describe captured statements, not necessarily complete request traces. Inconclusive pairs are excluded from comparison metrics and retained in audit counts. Text counts are heuristics, not parser-verified complexity.",
            "consistency_note": "STABLE means repeated structured values/order, not necessarily correct answers or identical prose.",
            "recommendation": "Review correctness, unresolved SQL evidence, matched latency and operational cost together. This experiment alone cannot establish that a full production redesign is needed."}


def show_sql_example(question, repetition=1):
    """Show captured SQL for both agents, when the saved evidence includes it."""
    state = load_checkpoint()
    for arm in ["A", "B"]:
        trial = state["trials"].get(trial_id(question, arm, repetition), {})
        reviews = trial.get("reviews", [])
        evidence = reviews[-1]["review"]["sql_evidence"] if reviews else []
        print(f"Agent {arm}: " + ("recorded SQL" if evidence else "SQL evidence is not available."))
        for entry in evidence:
            print(entry["text"])
            print(entry["correctness"], sql_counts(entry["text"]))


def show_report():
    """Display results and replace the derived report without changing trial evidence."""
    assert V2_SCORING_SELF_TESTS_PASSED, "Run the scorer checks in cell 11 before reporting."
    state = load_checkpoint()
    report = build_report(state)
    print("Sales AI V2 | Saved A/B comparison")
    print("Agreement with cross-checked reference calculations, not business-policy sign-off.")
    scope = report["question_scope"]
    print(f"Full target: {scope['full_target']} questions | {scope['prepared_in_this_batch']} prepared in this batch | {scope['remaining_pending']} still pending.")
    for arm, title in [("A", "Wide baseline"), ("B", "Booking-scope view")]:
        result = report["arms"][arm]
        print(f"\nAgent {arm} | {title}")
        correct = result["status_counts"].get("CORRECT", 0)
        accuracy = result["correctness_pct_of_evaluated"]
        accuracy_text = "not yet available" if accuracy is None else f"{accuracy:.1f}%"
        print(f"Answers: {accuracy_text} correct ({correct}/{result['evaluated']} evaluated; {result['evaluated']}/{result['planned']} planned runs evaluated).")
        received = result["submission_states"].get("RECEIVED", 0)
        matching_rows = result["row_correctness_counts"].get("CORRECT", 0)
        print(f"Original responses: {received}/{result['planned']} | Rows match: {matching_rows}/{result['rows_evaluated']} row comparisons.")
        latency = result["median_client_end_to_end_seconds"]
        latency_text = "unavailable" if latency is None else f"{latency:.2f} s"
        print(f"Median response time: {latency_text} ({result['timed_trials']} timed runs).")
    print("\nPer question: responses received / answers evaluated / correct (3 planned per agent)")
    print("Question | A       | B")
    for question in QUESTION_IDS:
        progress = []
        for arm in ["A", "B"]:
            keys = [trial_id(question, arm, repetition) for repetition in [1, 2, 3]]
            received = sum(state["trials"].get(key, {}).get("state") == "RECEIVED" for key in keys)
            statuses = [report["trial_scores"][key]["status"] for key in keys]
            evaluated = sum(status in {"CORRECT", "INCORRECT", "PARTIALLY_SUPPORTED", "UNSUPPORTED"} for status in statuses)
            progress.append(f"{received}/{evaluated}/{statuses.count('CORRECT')}")
        print(f"{question:<8} | {progress[0]:<7} | {progress[1]}")
    print("\nComplete comparison evidence:", report["first12_evidence_complete"])
    print("Matching rows alone do not verify claims, source usage, grain or complete SQL capture.")
    print("Agent instructions and warehouse use are not freshly verified here; differences do not prove architecture causality.")
    print("Response time is client latency, not SQL duration; missing measurements remain unavailable.")
    print("Uncertain/source-drift pairs are excluded. Full details and limitations are in the saved report.")
    print("Enrichment, threshold changes and swap scoring remain outside this batch.")
    with evidence_lock():
        latest = load_checkpoint()
        assert fingerprint(latest["trials"]) == fingerprint(state["trials"]), "Saved answer evidence changed while reporting. Rerun cell 14."
        latest["derived_report"] = report
        save_checkpoint(latest)
    return report


if globals().get("V2_BENCHMARK_READY") is not True or not all(
    callable(globals().get(name)) for name in ("load_checkpoint", "evidence_lock", "save_checkpoint", "validate_evidence_path")
):
    print("Report not loaded: this session's saved setup/helpers are not ready. The evidence file was not checked.")
    print("Run cells 1-7 and 9-11 first. Cell 12 sends pairs; cell 13 records their original answers.")
elif globals().get("V2_SCORING_SELF_TESTS_PASSED") is not True:
    print("Report not loaded: run the scorer checks in cells 10-11 first. The evidence file was not checked.")
elif globals().get("EVIDENCE_PATH") is None:
    print("Report not loaded: the evidence location is not configured. No file was checked. Run cells 2 and 7.")
else:
    validate_evidence_path()
    if EVIDENCE_PATH.exists():
        V2_REPORT = show_report()
    else:
        print("Report not loaded: the configured evidence file is missing.")
        print("If you expected saved results, investigate their location; do not start again or delete evidence.")
        print("For a new test, run cell 7 to save the setup, cell 12 for pairs, and cell 13 to record answers.")
```

## Notes for the handoff

The revised code has passed local regression and synthetic tests. It has not yet completed a live Databricks request. The earlier timeout's root cause remains unconfirmed. Do not report this client change as a proven fix or claim benchmark accuracy from successful manual chats.

Client behavior follows the [Databricks agent query guide](https://docs.databricks.com/aws/en/agents/custom-agents/query-agent) and the [OpenAI Python SDK reference](https://developers.openai.com/api/reference/python). OpenAI Docs was used for retry and raw-response handling; the configured destination remains the existing Databricks workspace.
