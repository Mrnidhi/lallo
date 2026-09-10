# Cell 3 | Measure each object at its intended grain

def profile_grain(item):
    frame = spark.table(item["table"])
    missing_columns = sorted(set(item["grain_columns"]) - set(frame.columns))

    if missing_columns:
        raise ValueError(
            item["name"]
            + " is missing expected grain columns: "
            + ", ".join(missing_columns)
        )

    grain_value = F.struct(
        *[F.col(column_name) for column_name in item["grain_columns"]]
    )

    result = frame.agg(
        F.count(F.lit(1)).alias("row_count"),
        F.countDistinct(grain_value).alias("distinct_grain_count"),
    ).first()

    row_count = int(result["row_count"])
    distinct_grain_count = int(result["distinct_grain_count"])
    repeated_rows = max(row_count - distinct_grain_count, 0)
    uniqueness_pct = (
        100.0
        if row_count == 0
        else 100.0 * distinct_grain_count / row_count
    )

    return {
        "display_order": item["order"],
        "object": item["name"],
        "row_meaning": item["row_meaning"],
        "row_count": row_count,
        "column_count": len(frame.columns),
        "distinct_grain_count": distinct_grain_count,
        "repeated_rows_at_grain": repeated_rows,
        "uniqueness_pct": round(uniqueness_pct, 2),
        "grain_check": (
            "ONE ROW PER GRAIN"
            if repeated_rows == 0
            else "REPEATED ROWS AT THIS GRAIN"
        ),
    }


grain_profiles = [profile_grain(item) for item in GRAIN_OBJECTS]

grain_schema = T.StructType(
    [
        T.StructField("display_order", T.IntegerType(), False),
        T.StructField("object", T.StringType(), False),
        T.StructField("row_meaning", T.StringType(), False),
        T.StructField("row_count", T.LongType(), False),
        T.StructField("column_count", T.IntegerType(), False),
        T.StructField("distinct_grain_count", T.LongType(), False),
        T.StructField("repeated_rows_at_grain", T.LongType(), False),
        T.StructField("uniqueness_pct", T.DoubleType(), False),
        T.StructField("grain_check", T.StringType(), False),
    ]
)

grain_summary = spark.createDataFrame(grain_profiles, grain_schema)

display(
    grain_summary
    .orderBy("display_order")
    .drop("display_order")
)

profile_by_name = {
    row["object"]: row
    for row in grain_profiles
}

final_objects = [
    "Booking fact",
    "Commitment fact",
    "Allocation fact",
    "Booking view",
]

assert all(
    profile_by_name[name]["repeated_rows_at_grain"] == 0
    for name in final_objects
), "A final object has more than one row at its intended grain."

wide = profile_by_name["Wide source"]
booking = profile_by_name["Booking fact"]
booking_view = profile_by_name["Booking view"]

assert booking["row_count"] == booking_view["row_count"], (
    "The booking fact and booking view should contain the same number of scopes."
)
assert wide["distinct_grain_count"] == booking_view["row_count"], (
    "The before and after booking populations do not match."
)

print("PASS: every final fact and view has one row per intended grain.")
