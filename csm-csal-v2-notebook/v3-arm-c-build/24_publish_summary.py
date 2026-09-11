# Databricks notebook source
# DBTITLE 1,Show the personal model ready for agent configuration

from pyspark.sql import functions as F


required_names = [
    "dimension_targets",
    "fact_targets",
    "business_views",
    "business_view_validation_df",
]

missing_names = [name for name in required_names if name not in globals()]
if missing_names:
    raise RuntimeError(
        "Run Cells 1 through 23 before showing the final summary. Missing: "
        + ", ".join(missing_names)
    )

if business_view_validation_df.filter(F.col("status") != "PASS").count():
    raise RuntimeError("One or more business views failed validation.")

summary_rows = []

for logical_name, target_name in sorted(dimension_targets.items()):
    summary_rows.append({
        "object_type": "DIMENSION",
        "logical_name": logical_name,
        "object_name": target_name,
        "row_count": int(spark.table(target_name).count()),
    })

for logical_name, target_name in sorted(fact_targets.items()):
    summary_rows.append({
        "object_type": "FACT",
        "logical_name": logical_name,
        "object_name": target_name,
        "row_count": int(spark.table(target_name).count()),
    })

for logical_name, target_name in sorted(business_views.items()):
    summary_rows.append({
        "object_type": "BUSINESS_VIEW",
        "logical_name": logical_name,
        "object_name": target_name,
        "row_count": int(spark.table(target_name).count()),
    })

published_model_summary_df = (
    spark.createDataFrame(summary_rows)
    .orderBy("object_type", "logical_name")
)

display(published_model_summary_df)

print("READY_FOR_V3_PERSONAL_AGENT_CONFIGURATION")
print("Arm C can use the 8 dimensions and 5 facts directly.")
print("Arm B can use the 5 business views.")
print("The same frozen August 2026 source version is used by both personal paths.")
