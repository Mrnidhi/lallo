# Databricks notebook source
# MAGIC %md
# MAGIC # CSM / CSAL grain analysis
# MAGIC
# MAGIC This notebook compares the frozen wide CSM source with the personal facts and booking view.
# MAGIC
# MAGIC It answers four questions:
# MAGIC
# MAGIC 1. What does one row mean in each object?
# MAGIC 2. How many repeated rows existed at the booking grain?
# MAGIC 3. How much smaller is the agent-facing view?
# MAGIC 4. Did the smaller view improve the completed agent test?
# MAGIC
# MAGIC This notebook is read-only. It does not create, replace or update any table.

# COMMAND ----------

# Imports and personal POC objects

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from pyspark.sql import functions as F
from pyspark.sql import types as T


PERSONAL_SCHEMA = "usr.jayarsr"

WIDE_SOURCE = (
    PERSONAL_SCHEMA
    + ".src_sales_ai_assistant_gold_csm_csal_summary_freeze_poc_v2_v23"
)
BOOKING_FACT = PERSONAL_SCHEMA + ".fact_booking_summary_poc_v2_v23"
COMMITMENT_FACT = PERSONAL_SCHEMA + ".fact_commitment_poc_v2_v23"
ALLOCATION_FACT = PERSONAL_SCHEMA + ".fact_allocation_poc_v2_v23"
BOOKING_VIEW = PERSONAL_SCHEMA + ".agent_booking_risk_current_poc_v2_v23"

BOOKING_GRAIN = ["customer", "agreement", "week_num", "service", "tcr"]
COMMITMENT_GRAIN = ["customer", "agreement", "week_num", "service"]
ALLOCATION_GRAIN = [
    "month",
    "week_num",
    "customer",
    "sales_rep",
    "agreement",
    "tcr",
    "service",
    "category",
]

GRAIN_OBJECTS = [
    {
        "order": 1,
        "name": "Wide source",
        "table": WIDE_SOURCE,
        "grain_columns": BOOKING_GRAIN,
        "row_meaning": "Existing rows viewed at booking scope",
    },
    {
        "order": 2,
        "name": "Booking fact",
        "table": BOOKING_FACT,
        "grain_columns": BOOKING_GRAIN,
        "row_meaning": "Customer + agreement + week + service + TCR",
    },
    {
        "order": 3,
        "name": "Commitment fact",
        "table": COMMITMENT_FACT,
        "grain_columns": COMMITMENT_GRAIN,
        "row_meaning": "Customer + agreement + week + service",
    },
    {
        "order": 4,
        "name": "Allocation fact",
        "table": ALLOCATION_FACT,
        "grain_columns": ALLOCATION_GRAIN,
        "row_meaning": "One detailed allocation slice",
    },
    {
        "order": 5,
        "name": "Booking view",
        "table": BOOKING_VIEW,
        "grain_columns": BOOKING_GRAIN,
        "row_meaning": "One agent-ready booking scope",
    },
]

PALETTE = {
    "wide": "#64748B",
    "booking": "#2563EB",
    "commitment": "#0F766E",
    "allocation": "#D97706",
    "view": "#7C3AED",
    "extra": "#F59E0B",
}

print("Ready to profile", len(GRAIN_OBJECTS), "personal objects.")

# COMMAND ----------

# Measure each object at its intended grain

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

# COMMAND ----------

# Show row counts and repeated rows

ordered_profiles = sorted(
    grain_profiles,
    key=lambda row: row["display_order"],
)

labels = [row["object"] for row in ordered_profiles]
row_counts = [row["row_count"] for row in ordered_profiles]
repeated_rows = [
    row["repeated_rows_at_grain"]
    for row in ordered_profiles
]
colors = [
    PALETTE["wide"],
    PALETTE["booking"],
    PALETTE["commitment"],
    PALETTE["allocation"],
    PALETTE["view"],
]

number_format = FuncFormatter(lambda value, _: f"{int(value):,}")

figure, axes = plt.subplots(1, 2, figsize=(16, 6))

row_bars = axes[0].barh(labels, row_counts, color=colors, height=0.62)
axes[0].invert_yaxis()
axes[0].set_title("Row count at each declared business grain", loc="left")
axes[0].set_xlabel("Rows")
axes[0].xaxis.set_major_formatter(number_format)
axes[0].grid(axis="x", alpha=0.18)
for side in ["top", "right", "left"]:
    axes[0].spines[side].set_visible(False)

for bar, value in zip(row_bars, row_counts):
    axes[0].text(
        value + max(row_counts) * 0.012,
        bar.get_y() + bar.get_height() / 2,
        f"{value:,}",
        va="center",
    )

axes[0].set_xlim(0, max(row_counts) * 1.2)

repeat_bars = axes[1].barh(
    labels,
    repeated_rows,
    color=PALETTE["extra"],
    height=0.62,
)
axes[1].invert_yaxis()
axes[1].set_title("Extra physical rows at the stated grain", loc="left")
axes[1].set_xlabel("Repeated rows")
axes[1].xaxis.set_major_formatter(number_format)
axes[1].grid(axis="x", alpha=0.18)
for side in ["top", "right", "left"]:
    axes[1].spines[side].set_visible(False)

for bar, value in zip(repeat_bars, repeated_rows):
    axes[1].text(
        value + max(max(repeated_rows), 1) * 0.025,
        bar.get_y() + bar.get_height() / 2,
        f"{value:,}",
        va="center",
    )

axes[1].set_xlim(0, max(max(repeated_rows), 1) * 1.25)

figure.suptitle("CSM / CSAL grain comparison", fontsize=16, fontweight="bold")
figure.text(
    0.5,
    0.01,
    "Each bar has a different row meaning. Only the repeated-row check is a duplication test.",
    ha="center",
    color="#475569",
)
figure.tight_layout(rect=[0, 0.04, 1, 0.96])
plt.show()
plt.close(figure)

removed_rows = wide["row_count"] - booking_view["row_count"]
reduction_pct = 100.0 * removed_rows / wide["row_count"]

print(
    f"The booking path removed {removed_rows:,} repeated physical rows "
    f"at booking grain, a {reduction_pct:.2f}% reduction."
)
print(
    "The commitment fact is smaller because commitment is stored once at its "
    "four-part grain. The allocation fact keeps its detailed rows intentionally."
)

# COMMAND ----------

# Compare what the agent sees and how the two paths performed

wide_columns = profile_by_name["Wide source"]["column_count"]
view_columns = profile_by_name["Booking view"]["column_count"]

agent_labels = ["Wide path", "Curated booking path"]
agent_colors = [PALETTE["wide"], PALETTE["view"]]
agent_columns = [wide_columns, view_columns]
agent_accuracy = [66.7, 72.2]
agent_latency = [40.98, 40.09]


def add_value_labels(axis, bars, values, suffix=""):
    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:g}{suffix}",
            ha="center",
            va="bottom",
        )


figure, axes = plt.subplots(1, 3, figsize=(17, 5.5))

column_bars = axes[0].bar(agent_labels, agent_columns, color=agent_colors, width=0.58)
axes[0].set_title("Columns exposed to the CSM agent")
axes[0].set_ylabel("Columns")
axes[0].set_ylim(0, max(agent_columns) * 1.18)
add_value_labels(axes[0], column_bars, agent_columns)

accuracy_bars = axes[1].bar(agent_labels, agent_accuracy, color=agent_colors, width=0.58)
axes[1].set_title("C01 to C06 table-answer accuracy")
axes[1].set_ylabel("Accuracy")
axes[1].set_ylim(0, 100)
axes[1].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0f}%"))
add_value_labels(axes[1], accuracy_bars, agent_accuracy, "%")

latency_bars = axes[2].bar(agent_labels, agent_latency, color=agent_colors, width=0.58)
axes[2].set_title("Median client response time")
axes[2].set_ylabel("Seconds")
axes[2].set_ylim(0, max(agent_latency) * 1.18)
add_value_labels(axes[2], latency_bars, agent_latency, " s")

for axis in axes:
    axis.grid(axis="y", alpha=0.18)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(axis="x", labelrotation=8)

figure.suptitle("Agent-facing before and after result", fontsize=16, fontweight="bold")
figure.text(
    0.5,
    0.01,
    "Latency is client end-to-end time. The small difference does not establish a speed winner.",
    ha="center",
    color="#475569",
)
figure.tight_layout(rect=[0, 0.05, 1, 0.96])
plt.show()
plt.close(figure)

print(
    f"The curated view exposes {wide_columns - view_columns} fewer columns "
    f"than the wide source."
)
print(
    "The curated path was one answer better in the completed benchmark. "
    "There was no clear latency winner."
)

# COMMAND ----------

# Keep the conclusion in one small table

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
