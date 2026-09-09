# Notebook cell 3 (file 28) | Read-only source checks
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
