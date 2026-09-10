# Cell 17 | Show the CSM-only benchmark result
# Reads saved evidence and updates only the derived aggregate report.
# It never sends an agent question or changes a data object.

assert callable(globals().get("build_report")), "Load the scoring and report cells first."
assert callable(globals().get("csm_load_checkpoint")), "Load the CSM-only checkpoint and runner first."
assert callable(globals().get("csm_evidence_lock"))
assert globals().get("V2_SCORING_SELF_TESTS_PASSED") is True


def percentile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def csm_results_report():
    state = csm_load_checkpoint()
    report = build_report(state)
    report["question_scope"] = {
        "formal_questions": len(QUESTION_IDS),
        "question_ids": list(QUESTION_IDS),
        "planned_trials": len(PLAN),
        "full_bank_context": 41,
        "questions_outside_this_poc": 41 - len(QUESTION_IDS),
    }
    report_labels = {
        "first12_evidence_complete": "csm_evidence_complete",
        "first12_answers_reviewed": "csm_answers_reviewed",
        "first12_answer_review_handoff_ready": "csm_answer_review_handoff_ready",
        "first12_grain_review_complete": "csm_grain_review_complete",
        "first12_sql_review_complete": "csm_sql_review_complete",
    }
    for old_name, new_name in report_labels.items():
        report[new_name] = report.pop(old_name)

    for arm in ("A", "B"):
        arm_report = report["arms"][arm]
        correct = arm_report["status_counts"].get("CORRECT", 0)
        planned = arm_report["planned"]
        arm_report["task_success_pct_of_planned"] = round(100 * correct / planned, 1)
        arm_plan = [item for item in PLAN if item["arm"] == arm]
        received = sum(
            state["trials"].get(item["trial_id"], {}).get("state") == "RECEIVED"
            for item in arm_plan
        )
        reviewed = sum(
            bool(state["trials"].get(item["trial_id"], {}).get("reviews"))
            for item in arm_plan
        )
        arm_report["received_pct_of_planned"] = round(100 * received / planned, 1)
        arm_report["reviewed_pct_of_planned"] = round(100 * reviewed / planned, 1)
        arm_report["evaluated_pct_of_planned"] = round(
            100 * arm_report["evaluated"] / planned,
            1,
        )

        correct_latencies = []
        received_latencies = []
        for item in PLAN:
            if item["arm"] != arm:
                continue
            trial = state["trials"].get(item["trial_id"])
            if not trial or trial.get("state") != "RECEIVED":
                continue
            seconds = trial.get("client_end_to_end_seconds")
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds):
                continue
            received_latencies.append(seconds)
            if report["trial_scores"][item["trial_id"]]["status"] == "CORRECT":
                correct_latencies.append(seconds)

        arm_report["received_latency"] = {
            "count": len(received_latencies),
            "median_seconds": statistics.median(received_latencies) if received_latencies else None,
            "q1_seconds": percentile(received_latencies, 0.25),
            "q3_seconds": percentile(received_latencies, 0.75),
        }
        arm_report["correct_only_latency"] = {
            "count": len(correct_latencies),
            "median_seconds": statistics.median(correct_latencies) if correct_latencies else None,
            "q1_seconds": percentile(correct_latencies, 0.25),
            "q3_seconds": percentile(correct_latencies, 0.75),
        }

    report["csm_answers_complete"] = report["csm_answers_reviewed"]
    report["interpretation"] = (
        "This compares the personal wide-table path with the personal curated booking-scope path "
        "for C01-C07 only. Any difference reflects the complete access path, including table shape, "
        "column naming, stored metrics, reader instructions and routing."
    )

    print("Sales AI V2 | CSM-only controlled comparison")
    print("Scope: 7 CSM questions, 3 repetitions, 21 planned runs per agent, 42 total.")
    for arm, name in (("A", "Wide baseline"), ("B", "Booking-scope view")):
        result = report["arms"][arm]
        counts = result["status_counts"]
        evaluated_accuracy = result["correctness_pct_of_evaluated"]
        evaluated_text = "unavailable" if evaluated_accuracy is None else f"{evaluated_accuracy:.1f}%"
        received_latency = result["received_latency"]
        latency_text = (
            "unavailable"
            if received_latency["median_seconds"] is None
            else f"{received_latency['median_seconds']:.2f} seconds"
        )
        print(f"\nAgent {arm} | {name}")
        print(
            "Primary task success:",
            f"{counts.get('CORRECT', 0)}/{result['planned']}",
            f"({result['task_success_pct_of_planned']:.1f}%)",
        )
        print("Accuracy among evaluated answers:", evaluated_text)
        print("Statuses:", counts)
        print("Median completed-response time:", latency_text)
        print("Captured SQL statements:", result["captured_sql_statements"])

    print("\nPer question: correct runs out of 3")
    print("Question | Wide | Booking view | Consistency A | Consistency B")
    for question in QUESTION_IDS:
        correct = {}
        for arm in ("A", "B"):
            keys = [trial_id(question, arm, repetition) for repetition in (1, 2, 3)]
            correct[arm] = sum(
                report["trial_scores"][key]["status"] == "CORRECT"
                for key in keys
            )
        consistency_a = report["arms"]["A"]["consistency"][question]
        consistency_b = report["arms"]["B"]["consistency"][question]
        print(
            f"{question:<8} | {correct['A']}/3  | {correct['B']}/3          | "
            f"{consistency_a:<13} | {consistency_b}"
        )

    received = sum(
        trial.get("state") == "RECEIVED"
        for trial in state["trials"].values()
    )
    reviewed = sum(bool(trial.get("reviews")) for trial in state["trials"].values())
    print(f"\nProgress: {received}/{len(PLAN)} responses received; {reviewed}/{len(PLAN)} reviewed.")
    print("Answer benchmark complete:", report["csm_answers_complete"])
    print("SQL evidence is reported only when the original trace is available.")
    print("Production smoke observations and the other 34 question-bank items are outside this score.")

    with csm_evidence_lock():
        latest = csm_load_checkpoint()
        assert fingerprint(latest["trials"]) == fingerprint(state["trials"]), (
            "Saved evidence changed while the report was being prepared. Run this cell again."
        )
        latest["derived_report"] = report
        save_checkpoint(latest)
    return report


CSM_REPORT = csm_results_report()
