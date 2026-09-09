# Notebook cell 5 (file 30) | Finance, cases, Daily Outlook and the two-domain question
# Read existing records only. Do not execute recommendations or deliverables.

V2_BENCHMARK_READY = False
assert "PREPARATION_STAMPS" in globals(), "Run notebook cells 3 and 4 successfully first."
invalidate_preparation("shared")
assert "booking" in PREPARATION_STAMPS, "Notebook cell 4 has not completed successfully."
require_preparation("booking", booking_payload())
# Remove an older shared draft before starting. A failed rerun cannot reuse it.
for question_id in ["D01", "D04", "D06", "D09", "R01"]:
    for answers in [GT, GT_SQL, GT_PARAMETERS, CONTRACTS]:
        answers.pop(question_id, None)
SALES_FIXTURES = None
latest_snapshot = SHARED["finance"].agg(F.max("snapshot_date").alias("latest")).first()["latest"]
assert latest_snapshot is not None, "Finance has no dated snapshot."
finance_snapshot = SHARED["finance"].filter(F.col("snapshot_date") == F.lit(latest_snapshot))
zero_child_cases = SHARED["cases"].join(SHARED["issues"].select("case_id"), "case_id", "left_anti")
current_outlooks = SHARED["outlook"].filter((F.col("task_name") == DAILY_OUTLOOK_TASK) & (F.col("is_current") == True))
assert current_outlooks.limit(1).count() == 1, "Verify the current Daily Outlook task_name. Do not guess another value."


def choose_rep(frame, column, override, label):
    candidates = frame.filter(F.col(column).isNotNull() & (F.trim(F.col(column)) != ""))
    if override is not None:
        assert isinstance(override, str) and override.strip()
        assert candidates.filter(F.col(column) == override).limit(1).count() == 1, label + ": exact representative has no qualifying rows."
        return override
    # Prefer a useful nonempty fixture; no answer has been generated yet.
    row = candidates.groupBy(column).count().orderBy(F.desc("count"), F.col(column).asc()).limit(1).collect()
    assert row, label + ": no nonempty fixture. Keep this test pending."
    return row[0][column]


SALES_FIXTURES = {
    "finance": choose_rep(finance_snapshot, "sales", SALES_OVERRIDES["finance"], "D01"),
    "cases": choose_rep(SHARED["cases"], "sales_name", SALES_OVERRIDES["cases"], "D04"),
    "no_issues": choose_rep(zero_child_cases, "sales_name", SALES_OVERRIDES["no_issues"], "D06"),
    "outlook": choose_rep(current_outlooks, "sales_name", SALES_OVERRIDES["outlook"], "D09"),
}
finance_columns = "customer total_outstanding max_aging_days ar_severity snapshot_date".split()
finance_ties = ["customer", "sales", "sales_full", "snapshot_date", "overdue_invoices", "max_aging_days", "ar_severity", "overdue_30_amount", "overdue_60_amount", "overdue_90_amount"]
finance_order = [F.col("total_outstanding").desc_nulls_last()] + [F.col(name).asc_nulls_last() for name in finance_ties]
finance_order_sql = "total_outstanding DESC NULLS LAST, " + ", ".join(name + " ASC NULLS LAST" for name in finance_ties)
fin_ref = finance_snapshot.filter(F.col("sales") == SALES_FIXTURES["finance"]).orderBy(*finance_order).limit(20)
fin_sql = "SELECT " + ", ".join(finance_columns) + " FROM " + SOURCES["finance"] + " WHERE snapshot_date = (SELECT max(snapshot_date) FROM " + SOURCES["finance"] + ") AND sales = :sales ORDER BY " + finance_order_sql + " LIMIT 20"
keep_answer("D01", fin_sql, {"sales": SALES_FIXTURES["finance"]}, fin_ref, fin_ref, finance_columns, {"total_outstanding": 6, "max_aging_days": None})

case_columns = "case_id customer_name state severity recommendation data_as_of_ts".split()
case_ref = SHARED["cases"].filter(F.col("sales_name") == SALES_FIXTURES["cases"]).orderBy(F.col("severity").desc_nulls_last(), F.col("case_id").asc()).limit(10)
case_sql = "SELECT " + ", ".join(case_columns) + " FROM " + SOURCES["cases"] + " WHERE sales_name = :sales ORDER BY severity DESC NULLS LAST, case_id ASC LIMIT 10"
keep_answer("D04", case_sql, {"sales": SALES_FIXTURES["cases"]}, case_ref, case_ref, case_columns, {"severity": 6})

no_issue_columns = ["case_id", "customer_name", "state"]
no_issue_ref = zero_child_cases.filter(F.col("sales_name") == SALES_FIXTURES["no_issues"]).orderBy("case_id").limit(20)
no_issue_sql = "SELECT c.case_id, c.customer_name, c.state FROM " + SOURCES["cases"] + " c WHERE c.sales_name = :sales AND NOT EXISTS (SELECT 1 FROM " + SOURCES["issues"] + " i WHERE i.case_id = c.case_id) ORDER BY c.case_id ASC LIMIT 20"
keep_answer("D06", no_issue_sql, {"sales": SALES_FIXTURES["no_issues"]}, no_issue_ref, no_issue_ref, no_issue_columns, {})
assert GT["D06"]["answer"], "Zero-child preservation needs a nonempty fixture."

outlook_columns = ["deliverable_id", "created_ts", "data_as_of"]
outlook_ref = current_outlooks.filter(F.col("sales_name") == SALES_FIXTURES["outlook"]).orderBy(F.col("created_ts").desc_nulls_last(), F.col("deliverable_id").asc()).limit(1)
outlook_sql = "SELECT deliverable_id, created_ts, data_as_of FROM " + SOURCES["outlook"] + " WHERE sales_name = :sales AND task_name = :task AND is_current = true ORDER BY created_ts DESC NULLS LAST, deliverable_id ASC LIMIT 1"
keep_answer("D09", outlook_sql, {"sales": SALES_FIXTURES["outlook"], "task": DAILY_OUTLOOK_TASK}, outlook_ref, outlook_ref, outlook_columns, {})
assert len(GT["D09"]["answer"]) == 1

# R01 keeps the two business processes separate. There is no customer join.
r_csm_columns = ["customer", "agreement", "tcr", "cancellation_pct"]
r_fin_columns = ["customer", "total_outstanding"]
GT["R01"] = {
    "booking": [{name: row[name] for name in r_csm_columns} for row in GT["C03"]["answer"][:10]],
    "finance": [{name: row[name] for name in r_fin_columns} for row in GT["D01"]["answer"][:5]],
}
GT_SQL["R01"] = {"booking": GT_SQL["C03"]["answer"].removesuffix("LIMIT 20") + "LIMIT 10",
                 "finance": fin_sql.removesuffix("LIMIT 20") + "LIMIT 5"}
GT_PARAMETERS["R01"] = {"week": FILTERS["week"], "service": FILTERS["service"], "sales": SALES_FIXTURES["finance"]}
CONTRACTS["R01"] = {
    "booking": {"columns": r_csm_columns, "precision": {"cancellation_pct": 2}},
    "finance": {"columns": r_fin_columns, "precision": {"total_outstanding": 6}},
}
assert source_markers() == SOURCE_MARKER, "Shared sources changed while preparing answers. Do not benchmark this draft."
preparation_stamp("shared", ground_truth_payload())
print("Shared-domain answers are independently checked, but still DRAFT pending review.")
print("Representative bindings are source-local. No cross-domain identity is implied.")
print("Finance currency and true upstream freshness are not established by these fields.")
