# Databricks notebook source
# DBTITLE 1,Publish the validated August model to the personal schema

from pyspark.sql import functions as F


required_names = [
    "candidate_dimensions",
    "candidate_facts",
    "DIMENSION_DEFINITIONS",
    "FACT_DEFINITIONS",
    "DIMENSION_LOOKUP",
    "primary_key_validation_df",
    "foreign_key_validation_df",
]

missing_names = [name for name in required_names if name not in globals()]
if missing_names:
    raise RuntimeError(
        "Run Cells 1 through 20 before publishing. Missing: "
        + ", ".join(missing_names)
    )

if final_decision != "READY_FOR_PERSONAL_ARM_C_POC_BUILD":
    raise RuntimeError("The validation notebook has not approved this model for publishing.")

if SOURCE_VERSION != 80 or TEST_MONTH != "August 2026":
    raise RuntimeError(
        "This build is frozen to source version 80 and August 2026. "
        f"Found version {SOURCE_VERSION!r} and month {TEST_MONTH!r}."
    )

current_user = spark.sql("SELECT current_user() AS user").first()["user"]
if current_user.lower() != "jayarsr@oocl.com":
    raise RuntimeError(f"Unexpected Databricks user: {current_user}")

failed_primary_keys = primary_key_validation_df.filter(
    F.col("primary_key_status") != "PASS"
).count()

failed_foreign_keys = foreign_key_validation_df.filter(
    F.col("foreign_key_status") != "PASS"
).count()

if failed_primary_keys or failed_foreign_keys:
    raise RuntimeError(
        "The in-memory model no longer passes its primary-key and foreign-key checks."
    )


PERSONAL_SCHEMA = "usr.jayarsr"
OBJECT_SUFFIX = "poc_v3_v80_aug2026"

dimension_targets = {
    name: f"{PERSONAL_SCHEMA}.{name}_{OBJECT_SUFFIX}"
    for name in sorted(candidate_dimensions)
}

fact_targets = {
    name: f"{PERSONAL_SCHEMA}.{name}_{OBJECT_SUFFIX}"
    for name in sorted(candidate_facts)
}

publish_targets = {**dimension_targets, **fact_targets}
publish_sources = {**candidate_dimensions, **candidate_facts}


# The target names are fixed. Overwrite makes a rerun idempotent while leaving
# every production object untouched.
for logical_name in sorted(publish_targets):
    target_name = publish_targets[logical_name]
    source_dataframe = publish_sources[logical_name]

    (
        source_dataframe.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(target_name)
    )

    spark.sql(
        f"""
        ALTER TABLE {target_name}
        SET TBLPROPERTIES (
          'poc.project' = 'csm_csal_v3',
          'poc.arm' = 'normalized_csm_csal',
          'poc.source_table' = '{SOURCE_TABLE}',
          'poc.source_version' = '{SOURCE_VERSION}',
          'poc.test_month' = '{TEST_MONTH}',
          'poc.owner' = 'jayarsr@oocl.com'
        )
        """
    )


published_rows = []

for logical_name in sorted(publish_targets):
    target_name = publish_targets[logical_name]
    expected_rows = publish_sources[logical_name].count()
    actual_rows = spark.table(target_name).count()

    published_rows.append({
        "logical_name": logical_name,
        "target_name": target_name,
        "expected_rows": int(expected_rows),
        "actual_rows": int(actual_rows),
        "status": "PASS" if expected_rows == actual_rows else "FAIL",
    })

publish_summary_df = (
    spark.createDataFrame(published_rows)
    .orderBy("logical_name")
)

display(publish_summary_df)

failed_publishes = publish_summary_df.filter(F.col("status") != "PASS").count()
if failed_publishes:
    raise RuntimeError(f"{failed_publishes} published tables have unexpected row counts.")

print("CELL_21_PERSONAL_MODEL_PUBLISHED")
print("Published 8 dimensions and 5 facts in usr.jayarsr.")
print("Production was not modified.")
