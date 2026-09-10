# Databricks notebook cell
# Explain benchmark misses without displaying customer-level result rows.

from collections import Counter
from html import escape
import json


if "CSM_FINAL_REPORT" not in globals():
    raise RuntimeError("Run the completed CSM scoring cell first.")

diagnostics = []
for question in CSM_EXPECTED_QUESTIONS:
    for arm in CSM_EXPECTED_ARMS:
        trials = [
            row
            for row in CSM_FINAL_REPORT["trial_scores"]
            if row["question"] == question and row["arm"] == arm
        ]
        status_counts = Counter(row["correctness"] for row in trials)
        reason_counts = Counter(
            row["reason"] or "No reason recorded"
            for row in trials
            if row["correctness"] != "CORRECT"
        )
        diagnostics.append(
            {
                "question": question,
                "arm": arm,
                "correct": status_counts.get("CORRECT", 0),
                "incorrect": status_counts.get("INCORRECT", 0),
                "not_evaluable": status_counts.get("NOT_EVALUABLE", 0),
                "reasons": [
                    {"count": count, "reason": reason}
                    for reason, count in reason_counts.most_common()
                ],
            }
        )


def reasons_text(item):
    if not item["reasons"]:
        return "All three answers matched the reference."
    return "; ".join(
        f"{entry['count']} time(s): {entry['reason']}"
        for entry in item["reasons"]
    )


rows_html = "".join(
    "<tr>"
    f"<td>{escape(item['question'])}</td>"
    f"<td>{escape(item['arm'])}</td>"
    f"<td>{item['correct']}/3</td>"
    f"<td>{escape(reasons_text(item))}</td>"
    "</tr>"
    for item in diagnostics
)

displayHTML(
    f"""
    <div style="font-family:Arial,sans-serif;max-width:1100px;color:#172033">
      <h2 style="margin:0 0 8px">Why answers did not pass</h2>
      <p style="margin:0 0 16px;color:#526176">
        These are scoring and presentation reasons only. No customer result rows are shown.
      </p>
      <table style="border-collapse:collapse;width:100%;font-size:15px">
        <thead><tr style="background:#e9eef7">
          <th style="text-align:left;padding:9px">Question</th>
          <th style="text-align:left;padding:9px">Path</th>
          <th style="text-align:left;padding:9px">Correct</th>
          <th style="text-align:left;padding:9px">Reason for remaining runs</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
)

print("CSM_BENCHMARK_DIAGNOSTICS=" + json.dumps(diagnostics, sort_keys=True))
