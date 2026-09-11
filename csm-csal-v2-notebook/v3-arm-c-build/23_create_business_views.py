# Databricks notebook source
# DBTITLE 1,Create the five personal CSM business views

from pyspark.sql import functions as F


required_names = [
    "fact_targets",
    "persisted_reconciliation_df",
    "persisted_primary_key_df",
    "persisted_foreign_key_df",
]

missing_names = [name for name in required_names if name not in globals()]
if missing_names:
    raise RuntimeError(
        "Run Cells 1 through 22 before creating the business views. Missing: "
        + ", ".join(missing_names)
    )

validation_frames = [
    persisted_reconciliation_df,
    persisted_primary_key_df,
    persisted_foreign_key_df,
]

if any(frame.filter(F.col("status") != "PASS").count() for frame in validation_frames):
    raise RuntimeError("The persisted model is not approved for view creation.")


PERSONAL_SCHEMA = "usr.jayarsr"
OBJECT_SUFFIX = "poc_v3_v80_aug2026"

view_sources = {
    "agent_csm_allocation": "fact_allocation",
    "agent_csm_booking": "fact_booking",
    "agent_csm_commitment": "fact_commitment",
    "agent_csm_monthly_performance": "fact_monthly_performance",
    "agent_csm_agreement_context": "fact_agreement_context",
}

business_views = {}

for view_name, fact_name in view_sources.items():
    target_view = f"{PERSONAL_SCHEMA}.{view_name}_{OBJECT_SUFFIX}"
    source_table = fact_targets[fact_name]

    spark.sql(
        f"""
        CREATE OR REPLACE VIEW {target_view}
        COMMENT 'Read-only CSM/CSAL V3 POC view for the August 2026 frozen comparison.'
        AS
        SELECT *
        FROM {source_table}
        """
    )

    business_views[view_name] = target_view


view_validation_rows = []

for view_name, target_view in business_views.items():
    fact_name = view_sources[view_name]
    source_table = fact_targets[fact_name]

    view_df = spark.table(target_view)
    source_df = spark.table(source_table)

    missing_rows = source_df.exceptAll(view_df.select(*source_df.columns)).count()
    unexpected_rows = view_df.select(*source_df.columns).exceptAll(source_df).count()

    view_validation_rows.append({
        "view_name": target_view,
        "source_table": source_table,
        "view_rows": int(view_df.count()),
        "source_rows": int(source_df.count()),
        "missing_rows": int(missing_rows),
        "unexpected_rows": int(unexpected_rows),
        "status": "PASS" if missing_rows == 0 and unexpected_rows == 0 else "FAIL",
    })

business_view_validation_df = (
    spark.createDataFrame(view_validation_rows)
    .orderBy("view_name")
)

display(business_view_validation_df)

failed_views = business_view_validation_df.filter(F.col("status") != "PASS").count()
if failed_views:
    raise RuntimeError(f"{failed_views} business views failed reconciliation.")

print("CELL_23_BUSINESS_VIEWS_READY")
print("Created five read-only personal views, one for each validated CSM grain.")
print("Production was not modified.")
