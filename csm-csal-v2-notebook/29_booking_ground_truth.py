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
