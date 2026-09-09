# Notebook cell 14 (file 39) | Re-score saved evidence and show before/after results
# This cell never submits questions. Re-running replaces only derived report data.


def sql_counts(text):
    # These are text heuristics, not a SQL parser or a SQL correctness check.
    cleaned = re.sub(r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", " ", text, flags=re.S)
    calls = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", cleaned)
    keywords = {"select", "as", "in", "over", "with", "exists", "values", "using", "partition"}
    return {"characters": len(text), "lines": len(text.splitlines()),
            "join_tokens": len(re.findall(r"\bJOIN\b", cleaned, flags=re.I)),
            "cte_candidates": len(re.findall(r"\bAS\s*\(\s*SELECT\b", cleaned, flags=re.I)),
            "function_like_tokens": sum(name.lower() not in keywords for name in calls)}


def score_trial(trial, reference):
    if trial is None:
        return {"status": "PENDING", "reason": "Not submitted."}
    if trial.get("source_check") != "STABLE":
        return {"status": "INCONCLUSIVE", "reason": "The source state during this trial is not verified stable."}
    if trial["state"] != "RECEIVED" or not trial.get("reviews"):
        return {"status": "NOT_EVALUABLE", "reason": "A reviewed original response is required."}
    review = trial["reviews"][-1]["review"]
    assert review["response_fingerprint"] == trial["response_fingerprint"] == fingerprint(trial["response"])
    question = trial["question"]
    scores = {}
    for section, contract in reference["contracts"][question].items():
        scores[section] = score_section(reference["expected"][question][section], review["sections"][section],
                                        contract["columns"], contract["precision"], review["aliases"][section], ordered=True)
    numeric_status = [result["status"] for result in scores.values()]
    if "NOT_EVALUABLE" in numeric_status:
        status = "NOT_EVALUABLE"
    elif review["answer_support"] != "SUPPORTED":
        status = review["answer_support"]  # Never counted as a correct supported answer.
    elif "INCORRECT" in numeric_status or not review["narrative_correct"]:
        status = "INCORRECT"
    elif question == "C07" and review["honest_no_match"] is not True:
        status = "INCORRECT"
    elif question == "R01" and review["sources_and_dates_correct"] is not True:
        status = "INCORRECT"
    else:
        status = "CORRECT"
    signature = None
    if all(result.get("actual_hash") for result in scores.values()):
        signature = fingerprint({section: result["actual_hash"] for section, result in scores.items()})
    sql_evidence = review["sql_evidence"]
    business_status = status
    if review["source_isolation"] == "INCORRECT":
        status = "INCONCLUSIVE"  # Correct numbers from an unassigned source are not valid architecture evidence.
    return {"status": status, "business_status": business_status, "sections": scores, "answer_signature": signature,
            "grain_correctness": review["grain_correctness"], "source_isolation": review["source_isolation"],
            "sql_correctness": [entry["correctness"] for entry in sql_evidence] or ["NOT_EVALUABLE"],
            "captured_sql_statement_count": len(sql_evidence),
            "sql_capture_complete": review.get("sql_capture_complete") is True,
            "sql_review_complete": bool(sql_evidence) and review.get("sql_capture_complete") is True
                                   and all(entry["correctness"] in {"CORRECT", "INCORRECT"} for entry in sql_evidence),
            "sql_complexity_heuristics": [sql_counts(entry["text"]) for entry in sql_evidence],
            "sql_execution_seconds": [entry.get("execution_seconds") for entry in sql_evidence]}


def build_report(state):
    def valid_seconds(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

    scores = {item["trial_id"]: score_trial(state["trials"].get(item["trial_id"]), state["manifest"]) for item in state["plan"]}
    # If either arm drifted, its paired architecture comparison is also inconclusive.
    bad_pairs = {(item["question"], item["repetition"]) for item in state["plan"] if scores[item["trial_id"]]["status"] == "INCONCLUSIVE"}
    for item in state["plan"]:
        if (item["question"], item["repetition"]) in bad_pairs and item["trial_id"] in state["trials"]:
            scores[item["trial_id"]]["status"] = "INCONCLUSIVE"
    arms = {}
    for arm in ["A", "B"]:
        items = [item for item in state["plan"] if item["arm"] == arm]
        comparison_items = [item for item in items if scores[item["trial_id"]]["status"] not in {"PENDING", "INCONCLUSIVE"}]
        excluded_items = [item for item in items if scores[item["trial_id"]]["status"] == "INCONCLUSIVE"]
        counts = Counter(scores[item["trial_id"]]["status"] for item in items)
        latencies = [state["trials"][item["trial_id"]].get("client_end_to_end_seconds") for item in comparison_items
                     if state["trials"].get(item["trial_id"], {}).get("state") == "RECEIVED"]
        latencies = [value for value in latencies if valid_seconds(value)]
        evaluated = sum(counts[key] for key in ["CORRECT", "INCORRECT", "PARTIALLY_SUPPORTED", "UNSUPPORTED"])
        captured_sql = [entry for item in comparison_items for entry in scores[item["trial_id"]].get("sql_complexity_heuristics", [])]
        sql_metrics = {name: statistics.median([entry[name] for entry in captured_sql]) if captured_sql else None
                       for name in ["characters", "lines", "join_tokens", "cte_candidates", "function_like_tokens"]}
        sql_seconds = [seconds for item in comparison_items for seconds in scores[item["trial_id"]].get("sql_execution_seconds", []) if valid_seconds(seconds)]
        sql_verdicts = Counter(verdict for item in comparison_items for verdict in scores[item["trial_id"]].get("sql_correctness", [])
                               if scores[item["trial_id"]].get("captured_sql_statement_count", 0) > 0)
        grain_verdicts = Counter(scores[item["trial_id"]].get("grain_correctness", "NOT_EVALUABLE") for item in comparison_items)
        isolation_verdicts = Counter(scores[item["trial_id"]].get("source_isolation", "NOT_EVALUABLE") for item in items)
        states = Counter(state["trials"][item["trial_id"]]["state"] if item["trial_id"] in state["trials"] else "NOT_SUBMITTED" for item in items)
        # Retain excluded evidence for audit, without mixing it into the comparison.
        audit_sql = [entry for item in items for entry in scores[item["trial_id"]].get("sql_complexity_heuristics", [])]
        audit_sql_verdicts = Counter(verdict for item in items for verdict in scores[item["trial_id"]].get("sql_correctness", [])
                                     if scores[item["trial_id"]].get("captured_sql_statement_count", 0) > 0)
        audit_grain_verdicts = Counter(scores[item["trial_id"]].get("grain_correctness", "NOT_EVALUABLE") for item in items)
        consistency = {}
        for question in QUESTION_IDS:
            group = [scores[trial_id(question, arm, repetition)] for repetition in [1, 2, 3]]
            hashes = [row.get("answer_signature") for row in group]
            if any(row["status"] in {"PENDING", "INCONCLUSIVE", "NOT_EVALUABLE"} for row in group) or any(value is None for value in hashes):
                consistency[question] = "NOT_EVALUABLE"
            else:
                consistency[question] = "STABLE" if len(set(hashes)) == 1 else "UNSTABLE"
        arms[arm] = {"planned": len(items), "status_counts": dict(counts), "evaluated": evaluated,
                     "correctness_pct_of_evaluated": round(100 * counts["CORRECT"] / evaluated, 1) if evaluated else None,
                     "median_client_end_to_end_seconds": statistics.median(latencies) if latencies else None,
                     "timed_trials": len(latencies), "consistency": consistency,
                     "submission_states": dict(states), "grain_verdicts": dict(grain_verdicts), "sql_verdicts": dict(sql_verdicts),
                     "source_isolation_verdicts": dict(isolation_verdicts),
                     "captured_sql_statements": len(captured_sql), "median_sql_text_heuristics": sql_metrics,
                     "timed_sql_statements": len(sql_seconds),
                     "trials_with_complete_sql_review": sum(scores[item["trial_id"]].get("sql_review_complete") is True for item in comparison_items),
                     "trials_without_captured_sql": sum(scores[item["trial_id"]].get("captured_sql_statement_count", 0) == 0 for item in comparison_items),
                     "median_sql_execution_seconds": statistics.median(sql_seconds) if sql_seconds else None,
                     "audit_all_captured_sql_statements": len(audit_sql), "audit_all_sql_verdicts": dict(audit_sql_verdicts),
                     "audit_all_grain_verdicts": dict(audit_grain_verdicts), "excluded_inconclusive_trials": len(excluded_items),
                     "excluded_captured_sql_statements": sum(scores[item["trial_id"]].get("captured_sql_statement_count", 0) for item in excluded_items)}
    paired_deltas = []
    for question in QUESTION_IDS:
        for repetition in [1, 2, 3]:
            keys = [trial_id(question, arm, repetition) for arm in ["A", "B"]]
            trials = [state["trials"].get(key) for key in keys]
            if all(scores[key]["status"] not in {"PENDING", "INCONCLUSIVE"} for key in keys) and all(trial and trial.get("state") == "RECEIVED" and trial.get("source_check") == "STABLE" and valid_seconds(trial.get("client_end_to_end_seconds")) for trial in trials):
                paired_deltas.append(trials[1]["client_end_to_end_seconds"] - trials[0]["client_end_to_end_seconds"])
    answers_reviewed = all(scores[item["trial_id"]]["status"] in {"CORRECT", "INCORRECT", "PARTIALLY_SUPPORTED", "UNSUPPORTED"} for item in state["plan"])
    isolation_verified = all(scores[item["trial_id"]].get("source_isolation") == "CORRECT" for item in state["plan"])
    grain_reviewed = all(scores[item["trial_id"]].get("grain_correctness") in {"CORRECT", "INCORRECT"} for item in state["plan"])
    sql_reviewed = all(scores[item["trial_id"]].get("sql_review_complete") is True for item in state["plan"])
    answer_handoff_ready = answers_reviewed and isolation_verified
    handoff_ready = answer_handoff_ready and grain_reviewed and sql_reviewed
    client_timing_complete = sum(arm["timed_trials"] for arm in arms.values()) == len(state["plan"])
    sql_timing_complete = sql_reviewed and all(
        len(scores[item["trial_id"]].get("sql_execution_seconds", [])) == scores[item["trial_id"]].get("captured_sql_statement_count", 0)
        and all(valid_seconds(value) for value in scores[item["trial_id"]].get("sql_execution_seconds", []))
        for item in state["plan"])
    return {"experiment_id": state["experiment_id"], "generated_at_utc": utc_now(), "arms": arms,
            "trial_scores": scores, "first12_evidence_complete": handoff_ready,
            "first12_answers_reviewed": answers_reviewed, "assigned_sources_verified_for_all_trials": isolation_verified,
            "first12_answer_review_handoff_ready": answer_handoff_ready,
            "first12_grain_review_complete": grain_reviewed, "first12_sql_review_complete": sql_reviewed,
            "client_response_timing_complete": client_timing_complete, "sql_execution_timing_complete": sql_timing_complete,
            "complete_timed_pairs": len(paired_deltas), "complete_timed_response_pairs": len(paired_deltas),
            "median_paired_B_minus_A_seconds": statistics.median(paired_deltas) if paired_deltas else None,
            "limitations": state["manifest"]["limitations"],
            "timing_note": "Client nonstreaming response latency, not SQL duration or exact UI latency. Timed pairs need not have correct or reviewed answers. Source checks are outside the timer. SQL timing availability is reported separately.",
            "evidence_note": "Complete review evidence requires reviewed answers, verified assigned sources, a resolved grain verdict and complete reviewed SQL capture for every trial. Incorrect findings still count as reviewed evidence. Missing platform timing remains explicitly unavailable and does not imply zero latency.",
            "sql_metrics_note": "SQL metrics describe captured statements, not necessarily complete request traces. Inconclusive pairs are excluded from comparison metrics and retained in audit counts. Text counts are heuristics, not parser-verified complexity.",
            "consistency_note": "STABLE means repeated structured values/order, not necessarily correct answers or identical prose.",
            "recommendation": "Review correctness, unresolved SQL evidence, matched latency and operational cost together. This experiment alone cannot establish that a full production redesign is needed."}


def show_sql_example(question, repetition=1):
    state = load_checkpoint()
    for arm in ["A", "B"]:
        trial = state["trials"].get(trial_id(question, arm, repetition), {})
        reviews = trial.get("reviews", [])
        evidence = reviews[-1]["review"]["sql_evidence"] if reviews else []
        print(arm, "recorded SQL:" if evidence else "SQL not available; no example fabricated.")
        for entry in evidence:
            print(entry["text"])
            print(entry["correctness"], sql_counts(entry["text"]))


def show_report():
    assert V2_SCORING_SELF_TESTS_PASSED
    state = load_checkpoint()
    report = build_report(state)
    print("Sales AI V2 | First 12 questions")
    for arm, title in [("A", "Wide baseline"), ("B", "Booking-scope view")]:
        result = report["arms"][arm]
        print(title, stable_json(result))
    print("Question | A: correct / 3 | B: correct / 3")
    for question in QUESTION_IDS:
        counts = [sum(report["trial_scores"][trial_id(question, arm, repetition)]["status"] == "CORRECT" for repetition in [1, 2, 3]) for arm in ["A", "B"]]
        print(question, counts[0], counts[1])
    print("First-batch evidence complete:", report["first12_evidence_complete"])
    print("Answers reviewed:", report["first12_answers_reviewed"], "Grain reviewed:", report["first12_grain_review_complete"],
          "Complete SQL capture reviewed:", report["first12_sql_review_complete"])
    print("Assigned-source usage verified for every trial:", report["assigned_sources_verified_for_all_trials"])
    print(report["timing_note"])
    print(report["evidence_note"])
    print(report["sql_metrics_note"])
    print("No before/after improvement is claimed until the results support it.")
    print("Full question bank, enrichment, receiver reliability and threshold calibration remain outside this batch.")
    with evidence_lock():
        latest = load_checkpoint()
        assert fingerprint(latest["trials"]) == fingerprint(state["trials"]), "Reviews changed while reporting. Rerun the report."
        latest["derived_report"] = report
        save_checkpoint(latest)
    return report


if ENABLE_EVIDENCE_SAVE and EVIDENCE_PATH.exists():
    V2_REPORT = show_report()
else:
    print("No stored experiment to report. No results have been invented.")
