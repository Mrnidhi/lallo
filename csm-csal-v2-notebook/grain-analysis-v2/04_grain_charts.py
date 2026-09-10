# Cell 4 | Show row counts and repeated rows

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
axes[0].set_title("Rows retained at each business grain", loc="left")
axes[0].set_xlabel("Rows")
axes[0].xaxis.set_major_formatter(number_format)
axes[0].grid(axis="x", alpha=0.18)
axes[0].spines[["top", "right", "left"]].set_visible(False)

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
axes[1].spines[["top", "right", "left"]].set_visible(False)

for bar, value in zip(repeat_bars, repeated_rows):
    axes[1].text(
        value + max(max(repeated_rows), 1) * 0.025,
        bar.get_y() + bar.get_height() / 2,
        f"{value:,}",
        va="center",
    )

axes[1].set_xlim(0, max(max(repeated_rows), 1) * 1.25)

figure.suptitle("CSM / CSAL grain comparison", fontsize=16, fontweight="bold")
figure.tight_layout()
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
