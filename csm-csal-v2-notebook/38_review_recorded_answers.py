# Notebook cell 13 (file 38) | Review original responses without asking new questions
# Copy values from actual saved responses, never from the expected-answer list.
# A final text response is not reliable SQL/trace evidence on its own.


def show_trial(question, arm, repetition):
    assert question in QUESTION_IDS and arm in ENDPOINTS and repetition in {1, 2, 3}
    state = load_checkpoint()
    key = trial_id(question, arm, repetition)
    assert key in state["trials"], "This trial has not been submitted."
    trial = state["trials"][key]
    print("Trial ID:", key, "State:", trial["state"], "Source check:", trial.get("source_check"))
    print("Recorded response fingerprint:", trial.get("response_fingerprint"))
    print(stable_json(trial.get("response")))
    return key


def review_template(question, arm, repetition):
    state = load_checkpoint()
    key = trial_id(question, arm, repetition)
    row = state["trials"][key]
    # None means not extracted. It must never be mistaken for an empty query result.
    return {
        "trial_key": key, "response_fingerprint": row.get("response_fingerprint"),
        "reviewer": "", "evidence_note": "",
        "sections": {name: None for name in MANIFEST["contracts"][question]},
        "aliases": {name: {} for name in MANIFEST["contracts"][question]},
        "alias_evidence": "", "narrative_correct": None,
        "honest_no_match": None, "sources_and_dates_correct": None,
        "answer_support": "SUPPORTED", "source_isolation": "NOT_EVALUABLE",
        "grain_correctness": "NOT_EVALUABLE", "sql_evidence": [],
        "sql_capture_complete": None, "sql_capture_note": "",
    }


def record_answer_review(review):
    assert isinstance(review, dict)
    assert review.get("reviewer", "").strip() and review.get("evidence_note", "").strip()
    assert isinstance(review.get("narrative_correct"), bool), "Review claims and qualifications, not just table numbers."
    assert review.get("answer_support") in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"}
    for field in ["source_isolation", "grain_correctness"]:
        assert review.get(field) in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}
    assert review.get("sql_capture_complete") is None or isinstance(review["sql_capture_complete"], bool)
    if review.get("sql_capture_complete") is True:
        assert review.get("sql_evidence") and review.get("sql_capture_note", "").strip(), "Complete SQL capture requires the original full trace/query evidence, not only a final answer snippet."
    with evidence_lock():
        state = load_checkpoint()
        trial = state["trials"][review["trial_key"]]
        assert trial["state"] == "RECEIVED", "No complete original response is available."
        assert review["response_fingerprint"] == trial["response_fingerprint"] == fingerprint(trial["response"])
        question = trial["question"]
        expected_sections = set(MANIFEST["contracts"][question])
        assert set(review["sections"]) == set(review["aliases"]) == expected_sections
        assert all(isinstance(rows, list) and all(isinstance(row, dict) for row in rows) for rows in review["sections"].values())
        if any(review["aliases"].values()):
            assert review.get("alias_evidence", "").strip(), "Verify aliases against the recorded SQL/source meaning, not name similarity."
        if question == "C07":
            assert isinstance(review.get("honest_no_match"), bool), "A query error or refusal is not a successful no-match answer."
        if question == "R01":
            assert isinstance(review.get("sources_and_dates_correct"), bool), "Review source names, separate dates and absence of an inferred customer join."
        for sql in review["sql_evidence"]:
            assert sql.get("text", "").strip() and sql.get("evidence_note", "").strip()
            assert sql.get("correctness") in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}
            seconds = sql.get("execution_seconds")
            assert seconds is None or (isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and math.isfinite(seconds) and seconds >= 0)
            if seconds is not None:
                assert sql.get("timing_evidence", "").strip(), "SQL duration needs query-history/trace evidence."
        history = trial.setdefault("reviews", [])
        cleaned = json.loads(stable_json(review))
        # Identical review reruns are no-ops. Corrections retain previous reviews.
        if not history or history[-1]["review"] != cleaned:
            history.append({"at_utc": utc_now(), "review": cleaned})
            save_checkpoint(state)
    print("Review saved for", question, trial["arm"], "repeat", trial["repetition"], "without new inference.")


print("Use show_trial('C01', 'A', 1), then review_template('C01', 'A', 1).")
print("Fill the template from that response and its genuine SQL/trace evidence, then call record_answer_review(review).")
print("Use plain numbers without commas or percent signs. Preserve NULL as None, not zero.")
print("Use ISO date/time text matching the recorded precision. Document any format conversion in evidence_note.")
print("Unavailable SQL, model details or timings must stay NOT_EVALUABLE/None. Do not invent them.")
