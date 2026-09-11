# Databricks notebook source
# DBTITLE 1,Re-read and validate the published personal model

from pyspark.sql import functions as F


required_names = [
    "candidate_dimensions",
    "candidate_facts",
    "DIMENSION_DEFINITIONS",
    "FACT_DEFINITIONS",
    "DIMENSION_LOOKUP",
    "dimension_targets",
    "fact_targets",
]

missing_names = [name for name in required_names if name not in globals()]
if missing_names:
    raise RuntimeError(
        "Run Cells 1 through 21 before validating the published model. Missing: "
        + ", ".join(missing_names)
    )


persisted_dimensions = {
    logical_name: spark.table(target_name)
    for logical_name, target_name in dimension_targets.items()
}

persisted_facts = {
    logical_name: spark.table(target_name)
    for logical_name, target_name in fact_targets.items()
}

persisted_tables = {**persisted_dimensions, **persisted_facts}
validated_sources = {**candidate_dimensions, **candidate_facts}


# First prove that every persisted table is identical to the validated
# in-memory dataframe, including nulls and duplicate rows.
reconciliation_rows = []

for logical_name in sorted(persisted_tables):
    expected_df = validated_sources[logical_name]
    actual_df = persisted_tables[logical_name].select(*expected_df.columns)

    missing_rows = expected_df.exceptAll(actual_df).count()
    unexpected_rows = actual_df.exceptAll(expected_df).count()

    reconciliation_rows.append({
        "table_name": logical_name,
        "expected_rows": int(expected_df.count()),
        "persisted_rows": int(actual_df.count()),
        "missing_rows": int(missing_rows),
        "unexpected_rows": int(unexpected_rows),
        "status": "PASS" if missing_rows == 0 and unexpected_rows == 0 else "FAIL",
    })

persisted_reconciliation_df = (
    spark.createDataFrame(reconciliation_rows)
    .orderBy("table_name")
)

print("Persisted-table reconciliation")
display(persisted_reconciliation_df)


# Validate primary keys again from the persisted tables.
primary_key_rows = []

for logical_name, dataframe in persisted_dimensions.items():
    primary_key = DIMENSION_DEFINITIONS[logical_name]["primary_key"]
    row_count = dataframe.count()
    distinct_keys = dataframe.select(primary_key).distinct().count()
    null_keys = dataframe.filter(F.col(primary_key).isNull()).count()

    primary_key_rows.append({
        "table_name": logical_name,
        "primary_key": primary_key,
        "row_count": int(row_count),
        "distinct_keys": int(distinct_keys),
        "null_keys": int(null_keys),
        "status": "PASS" if row_count == distinct_keys and null_keys == 0 else "FAIL",
    })

for logical_name, dataframe in persisted_facts.items():
    primary_key = FACT_DEFINITIONS[logical_name]["primary_key"]
    row_count = dataframe.count()
    distinct_keys = dataframe.select(primary_key).distinct().count()
    null_keys = dataframe.filter(F.col(primary_key).isNull()).count()

    primary_key_rows.append({
        "table_name": logical_name,
        "primary_key": primary_key,
        "row_count": int(row_count),
        "distinct_keys": int(distinct_keys),
        "null_keys": int(null_keys),
        "status": "PASS" if row_count == distinct_keys and null_keys == 0 else "FAIL",
    })

persisted_primary_key_df = (
    spark.createDataFrame(primary_key_rows)
    .orderBy("table_name")
)

print("Persisted primary-key validation")
display(persisted_primary_key_df)


# Validate every persisted fact-to-dimension foreign key.
foreign_key_rows = []

for fact_name, definition in FACT_DEFINITIONS.items():
    fact_df = persisted_facts[fact_name]

    for grain_column in definition["grain"]:
        if grain_column not in DIMENSION_LOOKUP:
            continue

        dimension_name, foreign_key = DIMENSION_LOOKUP[grain_column]
        dimension_df = persisted_dimensions[dimension_name]

        orphan_rows = (
            fact_df.select(foreign_key)
            .join(
                dimension_df.select(foreign_key),
                on=foreign_key,
                how="left_anti",
            )
            .count()
        )

        foreign_key_rows.append({
            "fact_table": fact_name,
            "foreign_key": foreign_key,
            "dimension_table": dimension_name,
            "orphan_rows": int(orphan_rows),
            "status": "PASS" if orphan_rows == 0 else "FAIL",
        })

persisted_foreign_key_df = (
    spark.createDataFrame(foreign_key_rows)
    .orderBy("fact_table", "foreign_key")
)

print("Persisted foreign-key validation")
display(persisted_foreign_key_df)


failed_reconciliations = persisted_reconciliation_df.filter(
    F.col("status") != "PASS"
).count()

failed_primary_keys = persisted_primary_key_df.filter(
    F.col("status") != "PASS"
).count()

failed_foreign_keys = persisted_foreign_key_df.filter(
    F.col("status") != "PASS"
).count()

if failed_reconciliations or failed_primary_keys or failed_foreign_keys:
    raise RuntimeError(
        "The persisted model failed validation: "
        f"reconciliation={failed_reconciliations}, "
        f"primary_keys={failed_primary_keys}, "
        f"foreign_keys={failed_foreign_keys}."
    )

print("CELL_22_PERSISTED_MODEL_VALIDATED")
print("All 13 tables match the approved in-memory model.")
print("All primary keys and foreign keys passed after re-reading from Delta.")
