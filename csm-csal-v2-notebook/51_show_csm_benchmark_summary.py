# Databricks notebook cell
# Show a readable aggregate summary of the completed CSM benchmark.

if "CSM_FINAL_REPORT" not in globals():
    raise RuntimeError("Run the completed CSM scoring cell first.")

report = CSM_FINAL_REPORT
arm_a = report["arms"]["A"]
arm_b = report["arms"]["B"]


def question_result(question, arm):
    trials = [
        row
        for row in report["trial_scores"]
        if row["question"] == question and row["arm"] == arm
    ]
    return sum(row["correctness"] == "CORRECT" for row in trials)


def seconds(value):
    return "Unavailable" if value is None else f"{value:.2f} seconds"


question_rows = []
for question in CSM_EXPECTED_QUESTIONS:
    question_rows.append(
        {
            "question": question,
            "wide_correct": question_result(question, "A"),
            "curated_correct": question_result(question, "B"),
            "wide_consistency": arm_a["consistency"][question],
            "curated_consistency": arm_b["consistency"][question],
        }
    )

summary = {
    "completed_trials": report["received_trials"],
    "planned_trials": report["planned_trials"],
    "reference_status": report["reference_status"],
    "wide": {
        "proven_correct": arm_a["correct"],
        "planned": arm_a["planned"],
        "evaluable": arm_a["evaluated"],
        "accuracy_pct": arm_a["correct_pct_of_evaluated"],
        "median_latency_seconds": arm_a["median_latency_seconds"],
        "stable_groups": arm_a["stable_question_groups"],
        "evaluable_groups": arm_a["evaluable_consistency_groups"],
    },
    "curated": {
        "proven_correct": arm_b["correct"],
        "planned": arm_b["planned"],
        "evaluable": arm_b["evaluated"],
        "accuracy_pct": arm_b["correct_pct_of_evaluated"],
        "median_latency_seconds": arm_b["median_latency_seconds"],
        "stable_groups": arm_b["stable_question_groups"],
        "evaluable_groups": arm_b["evaluable_consistency_groups"],
    },
    "median_paired_latency_b_minus_a_seconds": report["paired_latency"][
        "median_b_minus_a_seconds"
    ],
    "questions": question_rows,
}

metric_rows = [
    (
        "Proven correct",
        f"{arm_a['correct']}/{arm_a['planned']}",
        f"{arm_b['correct']}/{arm_b['planned']}",
    ),
    (
        "Accuracy on evaluable table answers",
        f"{arm_a['correct_pct_of_evaluated']:.1f}%",
        f"{arm_b['correct_pct_of_evaluated']:.1f}%",
    ),
    (
        "Stable evaluable question groups",
        f"{arm_a['stable_question_groups']}/{arm_a['evaluable_consistency_groups']}",
        f"{arm_b['stable_question_groups']}/{arm_b['evaluable_consistency_groups']}",
    ),
    (
        "Median response time",
        seconds(arm_a["median_latency_seconds"]),
        seconds(arm_b["median_latency_seconds"]),
    ),
    (
        "Clear no-match answers",
        f"{arm_a['c07_clear_no_match_narratives']}/3",
        f"{arm_b['c07_clear_no_match_narratives']}/3",
    ),
]

metric_html = "".join(
    "<tr>"
    f"<td>{escape(label)}</td>"
    f"<td>{escape(wide)}</td>"
    f"<td>{escape(curated)}</td>"
    "</tr>"
    for label, wide, curated in metric_rows
)
question_html = "".join(
    "<tr>"
    f"<td>{escape(row['question'])}</td>"
    f"<td>{row['wide_correct']}/3</td>"
    f"<td>{row['curated_correct']}/3</td>"
    f"<td>{escape(row['wide_consistency'])}</td>"
    f"<td>{escape(row['curated_consistency'])}</td>"
    "</tr>"
    for row in question_rows
)

displayHTML(
    f"""
    <div style="font-family:Arial,sans-serif;max-width:980px;color:#172033">
      <h2 style="margin:0 0 8px">CSM / CSAL controlled comparison</h2>
      <p style="margin:0 0 18px;color:#526176">
        {report['received_trials']} of {report['planned_trials']} planned responses completed.
        This compares the complete personal wide and curated access paths.
      </p>
      <table style="border-collapse:collapse;width:100%;font-size:16px;margin-bottom:22px">
        <thead><tr style="background:#e9eef7">
          <th style="text-align:left;padding:10px">Measure</th>
          <th style="text-align:left;padding:10px">Wide baseline</th>
          <th style="text-align:left;padding:10px">Curated booking view</th>
        </tr></thead>
        <tbody>{metric_html}</tbody>
      </table>
      <h3 style="margin:0 0 8px">Question-level evidence</h3>
      <table style="border-collapse:collapse;width:100%;font-size:15px">
        <thead><tr style="background:#e9eef7">
          <th style="text-align:left;padding:9px">Question</th>
          <th style="text-align:left;padding:9px">Wide correct</th>
          <th style="text-align:left;padding:9px">Curated correct</th>
          <th style="text-align:left;padding:9px">Wide consistency</th>
          <th style="text-align:left;padding:9px">Curated consistency</th>
        </tr></thead>
        <tbody>{question_html}</tbody>
      </table>
      <p style="margin:18px 0 0;color:#526176">
        C07 no-match wording was checked, but exact-filter SQL was not available in the saved responses.
        Latency is client end-to-end time, not SQL execution time.
      </p>
    </div>
    """
)

print("CSM_BENCHMARK_AGGREGATE=" + json.dumps(summary, sort_keys=True))
