# Cell 5 | Compare what the agent sees and how the two paths performed

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
    axis.spines[["top", "right"]].set_visible(False)
    axis.tick_params(axis="x", labelrotation=8)

figure.suptitle("Agent-facing before and after result", fontsize=16, fontweight="bold")
figure.tight_layout()
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
