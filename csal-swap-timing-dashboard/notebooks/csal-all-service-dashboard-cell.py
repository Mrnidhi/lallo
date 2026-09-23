# Databricks Python notebook cell. Run after the all-service timing cell and
# the allocation-candidate cell, in the same notebook session.
# Charts use aggregated data only. Source tables are not changed.

from pyspark.sql import functions as F
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

NAVY = "#203B5C"
RED = "#C8102E"
GREY = "#697586"
PALE = "#DCE2E8"

needed = ("csal_service_coverage", "csal_service_summary", "csal_daily_curve")
missing = [name for name in needed if name not in globals()]
if missing:
    raise RuntimeError(
        "Run the all-service timing cell first. Missing: " + ", ".join(missing)
    )
if "changes" not in globals() or "pair_status" not in globals():
    raise RuntimeError("Run the allocation-candidate cell first.")
if not spark.catalog.tableExists(changes) or not spark.catalog.tableExists(pair_status):
    raise RuntimeError("Allocation temporary views expired; rerun that cell first.")

coverage = csal_service_coverage
timing = csal_service_summary
daily = csal_daily_curve

totals = coverage.agg(
    F.sum("source_shipments").alias("source"),
    F.sum("matured_direct_matches").alias("direct"),
).first()
timing_totals = timing.agg(
    F.sum("records_in_28_before_14_after_window").alias("window"),
    F.sum("before_cutoff").alias("before"),
    F.sum("after_cutoff").alias("after"),
    F.sum("at_cutoff").alias("at"),
).first()
source_n = int(totals["source"] or 0)
direct_n = int(totals["direct"] or 0)
window_n = int(timing_totals["window"] or 0)
before_n = int(timing_totals["before"] or 0)
after_n = int(timing_totals["after"] or 0)
at_n = int(timing_totals["at"] or 0)
after_pct = 100 * after_n / window_n if window_n else 0

day_rows = (
    daily.filter(F.col("service") == "ALL SERVICES")
    .select("day_bucket_from_cutoff", "records_created", "cumulative_pct_of_window")
    .orderBy("day_bucket_from_cutoff")
    .collect()
)
days = [int(r["day_bucket_from_cutoff"]) for r in day_rows]
day_counts = [int(r["records_created"]) for r in day_rows]
cum_pct = [float(r["cumulative_pct_of_window"]) for r in day_rows]

coverage_rows = (
    coverage.filter(F.col("service").isNotNull())
    .orderBy(F.desc("source_shipments"), "service")
    .limit(10).collect()
)
largest_services = [r["service"] for r in coverage_rows]
timing_by_service = {
    r["service"]: r for r in timing.filter(F.col("service").isin(largest_services)).collect()
}

if not day_rows or window_n == 0:
    raise RuntimeError(
        "No comparable all-service timing records. Review the coverage output; "
        "the dashboard will not draw an empty curve as a finding."
    )

print("CSAL shipment-record timing and allocation revisions | all services")
print(
    f"Eligible timing coverage: {direct_n:,} matured route-and-cutoff records from "
    f"{source_n:,} current booking-detail shipments in the selected source period "
    f"({100 * direct_n / source_n:.1f}%); "
    f"{window_n:,} fall within the common 28-day-before/14-day-after window."
    if source_n else "Timing coverage: no source records."
)
print(
    "The current route check uses corporate voyage and loading port. "
    "Booking and stop sail-week alignment remains unresolved and is not "
    "an eligibility condition for this timing curve."
)
print(
    f"Within that window, {before_n:,} records were created before the "
    f"TCR cutoff, {at_n:,} exactly at it, and {after_n:,} after it "
    f"({after_pct:.1f}% after)."
)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": PALE, "axes.labelcolor": NAVY,
    "xtick.color": GREY, "ytick.color": GREY,
})

fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
fig.suptitle("CSAL record creation relative to TCR cutoff | eligible timing records", color=NAVY,
             fontsize=17, fontweight="bold", x=0.02, ha="left")

# A daily count curve shows the shape, including observations after cutoff.
ax = axes[0, 0]
ax.plot(days, day_counts, color=NAVY, linewidth=2.5, marker="o", markersize=3)
ax.axvline(-0.5, color=RED, linewidth=1.8, linestyle="--")
ax.text(0, max(day_counts) * 0.91, "TCR cutoff", color=RED, fontsize=9)
ax.set(title="Daily record creation in the comparable window",
       xlabel="Day bucket (0 = first 24 hours after cutoff)",
       ylabel="Shipment records")
ax.set_xlim(min(days), max(days))
ax.yaxis.set_major_locator(MaxNLocator(integer=True))
ax.grid(axis="y", color=PALE, linewidth=0.7)

# The denominator here is all records in the common 28/14-day window.
ax = axes[0, 1]
boundary_days = [d + 1 for d in days]
ax.plot(boundary_days, cum_pct, color=NAVY, linewidth=2.7,
        drawstyle="steps-post")
ax.axvline(0, color=RED, linewidth=1.8, linestyle="--")
ax.set(title="Cumulative share of records in the window",
       xlabel="Days to cutoff (0 = cutoff instant)",
       ylabel="Share of comparable window records (%)",
       ylim=(0, 103), xlim=(min(days), max(days) + 1))
ax.grid(axis="y", color=PALE, linewidth=0.7)
for target, label in [(-15, "By 14 days before"), (-8, "By 7 days before"), (-1, "By cutoff")]:
    point = next((r for r in day_rows if r["day_bucket_from_cutoff"] == target), None)
    if point is not None:
        y = float(point["cumulative_pct_of_window"])
        ax.scatter([target + 1], [y], color=RED, s=30, zorder=3)
        ax.annotate(f"{label}: {y:.1f}%", (target + 1, y),
                    xytext=(5, -15 if target == -1 else 8),
                    textcoords="offset points", color=NAVY, fontsize=8)

# Coverage is essential: timing percentages are not representative where it is low.
ax = axes[1, 0]
labels = [r["service"] for r in reversed(coverage_rows)]
denoms = [int(r["source_shipments"]) for r in reversed(coverage_rows)]
numerators = [int(r["matured_direct_matches"]) for r in reversed(coverage_rows)]
values = [100 * n / d if d else 0 for n, d in zip(numerators, denoms)]
ax.barh(labels, values, color=NAVY, height=0.62)
for i, (v, n, d) in enumerate(zip(values, numerators, denoms)):
    ax.text(v + 1, i, f"{v:.0f}%  ({n:,}/{d:,})", va="center", fontsize=8,
            color=NAVY)
ax.set(title="Eligible timing coverage: 10 largest source services",
       xlabel="Share of current booking-detail shipments (%)", xlim=(0, 125))
ax.grid(axis="x", color=PALE, linewidth=0.7)
ax.set_axisbelow(True)

ax = axes[1, 1]
labels = list(reversed(largest_services))
values = [float(timing_by_service[s]["after_pct_of_comparable"] or 0)
          if s in timing_by_service else 0 for s in labels]
ns = [int(timing_by_service[s]["records_in_28_before_14_after_window"])
      if s in timing_by_service else 0 for s in labels]
ax.barh(labels, values, color=[RED if n else PALE for n in ns], height=0.62)
for i, (v, n) in enumerate(zip(values, ns)):
    label = f"{v:.1f}%  (n={n:,})" if n else "N/A (no comparable records)"
    ax.text(v + 0.7, i, label, va="center", fontsize=8,
            color=NAVY)
ax.set(title="After cutoff: same 10 largest source services",
       xlabel="Share of comparable window records (%)",
       xlim=(0, max(values + [1]) * 1.35))
ax.grid(axis="x", color=PALE, linewidth=0.7)
ax.set_axisbelow(True)
plt.show()

# Allocation activity is kept distinct from shipment-record activity.
weekday_rows = spark.sql(f"""
SELECT DATE_FORMAT(raw_update_date, 'EEEE') AS weekday,
       SUM(CASE WHEN delta_teu > 0 THEN delta_teu ELSE 0 END) AS increase_teu,
       -SUM(CASE WHEN delta_teu < 0 THEN delta_teu ELSE 0 END) AS decrease_teu
FROM {changes}
WHERE delta_teu <> 0 AND raw_update_date IS NOT NULL
GROUP BY DATE_FORMAT(raw_update_date, 'EEEE')
""").collect()
weekday_map = {r["weekday"]: r for r in weekday_rows}
weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]
up = [float(weekday_map[d]["increase_teu"] or 0) if d in weekday_map else 0
      for d in weekdays]
down = [float(weekday_map[d]["decrease_teu"] or 0) if d in weekday_map else 0
        for d in weekdays]

pair_rows = spark.sql(f"""
SELECT service, evidence_status,
       COUNT(*) AS candidate_pairs,
       SUM(candidate_teu) AS candidate_teu
FROM {pair_status}
GROUP BY service, evidence_status
""").collect()
pair_n = sum(int(r["candidate_pairs"]) for r in pair_rows)
usable_n = sum(int(r["candidate_pairs"]) for r in pair_rows
               if r["evidence_status"] == "BOTH_SIDES_EXACT_AND_AUDITED")
unresolved_n = pair_n - usable_n
print(
    f"Allocation screening: {pair_n:,} balanced two-plan revision candidates; "
    f"{usable_n:,} pass the current-route, week, cutoff and audit checks. "
    "They are not confirmed swaps."
)
print("Rerun the corrected allocation-candidate cell before presenting these screening counts.")

candidate_days = spark.sql(f"""
SELECT DATEDIFF(raw_update_date,
       LEAST(decrease_cutoff_utc_date, increase_cutoff_utc_date)) AS day,
       COUNT(*) AS candidate_pairs
FROM {pair_status}
WHERE evidence_status = 'BOTH_SIDES_EXACT_AND_AUDITED'
  AND raw_update_date IS NOT NULL
  AND decrease_cutoff_utc_date IS NOT NULL
  AND increase_cutoff_utc_date IS NOT NULL
GROUP BY DATEDIFF(raw_update_date,
         LEAST(decrease_cutoff_utc_date, increase_cutoff_utc_date))
ORDER BY day
""").collect()

fig, axes = plt.subplots(2, 2, figsize=(16, 9), constrained_layout=True)
fig.suptitle("When are allocation changes recorded?", color=NAVY,
             fontsize=17, fontweight="bold", x=0.02, ha="left")

ax = axes[0, 0]
x = list(range(7))
ax.bar([i - 0.19 for i in x], up, width=0.38, color=NAVY, label="Increase")
ax.bar([i + 0.19 for i in x], down, width=0.38, color=RED, label="Decrease")
ax.set_xticks(x)
ax.set_xticklabels([d[:3] for d in weekdays])
ax.set(title="Allocation changes by raw update weekday",
       ylabel="Absolute TEU changed")
ax.legend(frameon=False)
ax.grid(axis="y", color=PALE, linewidth=0.7)
ax.set_axisbelow(True)

ax = axes[0, 1]
ax.barh(["Route, week, cutoff and audit checks", "One or more checks unresolved"],
        [usable_n, unresolved_n], color=[NAVY, RED], height=0.45)
for i, val in enumerate([usable_n, unresolved_n]):
    ax.text(val + 0.2, i, f"{val:,}", va="center", color=NAVY)
ax.set(title="Balanced revision-pair screening (provisional)", xlabel="Candidate pairs",
       xlim=(0, max(pair_n, 1) * 1.22))
ax.grid(axis="x", color=PALE, linewidth=0.7)
ax.set_axisbelow(True)

ax = axes[1, 0]
if candidate_days:
    xs = [int(r["day"]) for r in candidate_days]
    ys = [int(r["candidate_pairs"]) for r in candidate_days]
    ax.bar(xs, ys, color=[NAVY if d < 0 else RED for d in xs], width=0.8)
    ax.axvline(0, color=RED, linewidth=1.4, linestyle="--")
    ax.set(title="Candidate raw update dates vs current cutoffs",
           xlabel="Raw calendar day minus UTC cutoff day (provisional)",
           ylabel="Candidate pairs")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
else:
    ax.text(0.5, 0.55, "No pair passed route, cutoff, and audit checks",
            ha="center", va="center", color=NAVY, fontsize=12,
            transform=ax.transAxes)
    ax.text(0.5, 0.42, "A before/after swap curve cannot yet be calculated.",
            ha="center", va="center", color=GREY, fontsize=10,
            transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])

ax = axes[1, 1]
by_service = {}
for r in pair_rows:
    service = r["service"] or "Unknown"
    row = by_service.setdefault(service, {"usable": 0, "unresolved": 0})
    key = "usable" if r["evidence_status"] == "BOTH_SIDES_EXACT_AND_AUDITED" else "unresolved"
    row[key] += int(r["candidate_pairs"])
top = sorted(by_service.items(),
             key=lambda item: -(item[1]["usable"] + item[1]["unresolved"]))[:10]
if top:
    top = list(reversed(top))
    names = [item[0] for item in top]
    good = [item[1]["usable"] for item in top]
    other = [item[1]["unresolved"] for item in top]
    ax.barh(names, good, color=NAVY, label="Route, week, cutoff and audit checks")
    ax.barh(names, other, left=good, color=RED, label="Unresolved")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    ax.set(title="Candidate evidence by service", xlabel="Candidate pairs")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="x", color=PALE, linewidth=0.7)
    ax.set_axisbelow(True)
else:
    ax.text(0.5, 0.5, "No balanced revision pairs in this period",
            ha="center", va="center", color=NAVY, fontsize=11,
            transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])
plt.show()

print(
    "Reading guide: these curves show the shipment-creation timestamp, not "
    "confirmed original booking time or how much final TEU was known. The "
    "timing cohort does not enforce sail-week alignment. The "
    "weekday chart uses the raw change-log date; its timezone is unconfirmed. "
    "Candidate timing uses current route/cutoff data and is provisional. "
    "A recommendation date cannot be justified until original booking times, "
    "historical cutoffs, and the business meaning of paired edits are confirmed."
)
