# Cell 41 | Render aggregate benchmark visuals
# Read-only. This cell never prints responses, identifiers, SQL text, or business rows.

import json
from pathlib import Path

import matplotlib.pyplot as plt


chart_evidence_path = Path(
    globals().get(
        "CSM_EVIDENCE_PATH",
        "/Workspace/Users/jayarsr@oocl.com/Sales AI EDA/v2-benchmark-csm-controlled-evidence.json",
    )
)

if not chart_evidence_path.exists():
    print("Aggregate chart not loaded: the CSM-only checkpoint is not available.")
else:
    checkpoint = json.loads(chart_evidence_path.read_text(encoding="utf-8"))
    report = checkpoint.get("derived_report")
    if not isinstance(report, dict) or not isinstance(report.get("arms"), dict):
        print("Aggregate chart not loaded: run the report cell first.")
    else:
        arms = report["arms"]
        labels = ["A | Wide baseline", "B | Booking scope"]
        keys = ["A", "B"]

        def value(arm, key):
            result = arms.get(arm, {})
            return result.get(key)

        def status_count(arm, statuses):
            counts = arms.get(arm, {}).get("status_counts", {})
            return sum(counts.get(status, 0) for status in statuses)

        def source_count(arm, verdict):
            return arms.get(arm, {}).get("source_isolation_verdicts", {}).get(verdict, 0)

        task_success = [value(arm, "task_success_pct_of_planned") or 0 for arm in keys]
        client_latency = [value(arm, "median_client_end_to_end_seconds") for arm in keys]
        sql_latency = [value(arm, "median_sql_execution_seconds") for arm in keys]
        sql_latency_plot = [x if x is not None else 0 for x in sql_latency]

        fig, axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
        fig.suptitle("Sales AI V2 | CSM architecture benchmark", fontsize=15)

        axes[0, 0].bar(labels, task_success, color=["#3568a8", "#e07a35"])
        axes[0, 0].set_title("Correct answers out of all planned runs")
        axes[0, 0].set_ylabel("Percent")
        axes[0, 0].set_ylim(0, 100)

        status_groups = [
            ("CORRECT", ["CORRECT"]),
            ("INCORRECT", ["INCORRECT"]),
            ("PARTIAL / UNSUPPORTED", ["PARTIALLY_SUPPORTED", "UNSUPPORTED"]),
            ("NOT EVALUATED", ["NOT_EVALUABLE", "INCONCLUSIVE"]),
            ("PENDING", ["PENDING"]),
        ]
        bottom = [0, 0]
        colors = ["#4c9f70", "#c94c4c", "#d79d31", "#8064a2", "#9aa0a6"]
        for (label, statuses), color in zip(status_groups, colors):
            counts = [status_count(arm, statuses) for arm in keys]
            axes[0, 1].bar(labels, counts, bottom=bottom, label=label, color=color)
            bottom = [left + right for left, right in zip(bottom, counts)]
        axes[0, 1].set_title("Trial status counts")
        axes[0, 1].set_ylabel("Trials")
        axes[0, 1].legend(fontsize=8)

        axes[0, 2].bar(labels, [x or 0 for x in client_latency], color=["#3568a8", "#e07a35"])
        axes[0, 2].set_title("Median client latency")
        axes[0, 2].set_ylabel("Seconds; zero means unavailable")

        axes[1, 0].bar(labels, sql_latency_plot, color=["#3568a8", "#e07a35"])
        axes[1, 0].set_title("Median SQL latency")
        axes[1, 0].set_ylabel("Seconds; zero means unavailable")

        source_statuses = ["CORRECT", "INCORRECT", "NOT_EVALUABLE"]
        bottom = [0, 0]
        for status, color in zip(source_statuses, ["#4c9f70", "#c94c4c", "#9aa0a6"]):
            counts = [source_count(arm, status) for arm in keys]
            axes[1, 1].bar(labels, counts, bottom=bottom, label=status, color=color)
            bottom = [left + right for left, right in zip(bottom, counts)]
        axes[1, 1].set_title("Source / routing verdicts")
        axes[1, 1].set_ylabel("Trials")
        axes[1, 1].legend(fontsize=8)

        axes[1, 2].axis("off")
        axes[1, 2].text(
            0,
            1,
            "Scope\n"
            f"Experiment: {report.get('experiment_id', 'unavailable')}\n"
            f"Formal questions: {report.get('question_scope', {}).get('formal_questions', 'unavailable')}\n"
            f"Planned trials: {report.get('question_scope', {}).get('planned_trials', 'unavailable')}\n"
            f"Complete timed pairs: {report.get('complete_timed_pairs', 'unavailable')}\n"
            f"Paired B minus A latency: {report.get('median_paired_B_minus_A_seconds', 'unavailable')}\n\n"
            "Notes\n"
            "Missing SQL evidence remains unavailable.\n"
            "This view contains aggregate checkpoint metrics only.",
            va="top",
            fontsize=10,
        )
        plt.show()

        print("Rendered aggregate metrics only: correctness, status, client latency, SQL latency, and source/routing verdicts.")
