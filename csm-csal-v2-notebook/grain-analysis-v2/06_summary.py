# Cell 6 | Keep the conclusion in one small table

removed_rows = wide["row_count"] - booking_view["row_count"]
removed_pct = 100.0 * removed_rows / wide["row_count"]
removed_columns = wide["column_count"] - booking_view["column_count"]
column_reduction_pct = 100.0 * removed_columns / wide["column_count"]

comparison = [
    (
        "Rows presented at booking grain",
        f"{wide['row_count']:,}",
        f"{booking_view['row_count']:,}",
        f"{removed_rows:,} repeated rows removed ({removed_pct:.2f}%)",
    ),
    (
        "Columns exposed to the CSM agent",
        str(wide["column_count"]),
        str(booking_view["column_count"]),
        f"{removed_columns} fewer columns ({column_reduction_pct:.1f}%)",
    ),
    (
        "C01 to C06 table-answer accuracy",
        "66.7%",
        "72.2%",
        "Curated path was one answer better",
    ),
    (
        "Median client response time",
        "40.98 seconds",
        "40.09 seconds",
        "No clear latency winner",
    ),
]

comparison_schema = T.StructType(
    [
        T.StructField("measure", T.StringType(), False),
        T.StructField("wide_path", T.StringType(), False),
        T.StructField("curated_path", T.StringType(), False),
        T.StructField("meaning", T.StringType(), False),
    ]
)

display(spark.createDataFrame(comparison, comparison_schema))

print("Conclusion")
print("The final facts and booking view have one row per intended grain.")
print("The curated booking view is smaller and produced a modest accuracy improvement.")
print("Production remains unchanged. The curated view should continue as a pilot.")
