# Notebook cell 13 (file 38) | Check and record the saved answers
# Copy answer values from the saved response, not the reference rows.
# For SQL checks, use the original query or trace; final-answer text alone is insufficient.


def show_trial(question, arm, repetition):
    """Display one saved response without sending another question."""
    assert question in QUESTION_IDS and arm in ENDPOINTS and repetition in {1, 2, 3}, (
        "Choose a listed question, arm A or B, and repetition 1, 2 or 3."
    )
    state = load_checkpoint()
    key = trial_id(question, arm, repetition)
    assert key in state["trials"], (
        "No saved trial exists for this selection. Use cell 12 to run the next planned pair."
    )
    trial = state["trials"][key]
    print(f"{question} | Agent {arm} | Repetition {repetition}")
    print("Trial ID:", key)
    print("State:", trial["state"], "| Source check:", trial.get("source_check"))
    print("Response fingerprint:", trial.get("response_fingerprint"))
    print("Saved response:")
    print(stable_json(trial.get("response")))
    return key


def review_template(question, arm, repetition):
    """Create an unfilled record for one saved answer and its supporting evidence."""
    state = load_checkpoint()
    key = trial_id(question, arm, repetition)
    row = state["trials"][key]
    # None means not yet copied; [] means a confirmed empty result.
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
    """Save a completed answer check; identical reruns leave the history unchanged."""
    assert isinstance(review, dict), "Pass the completed dictionary returned by review_template()."
    assert review.get("reviewer", "").strip() and review.get("evidence_note", "").strip(), (
        "Fill reviewer and evidence_note with who checked the answer and what supports it."
    )
    assert isinstance(review.get("narrative_correct"), bool), (
        "Set narrative_correct after checking the claims and qualifications as well as the numbers."
    )
    assert review.get("answer_support") in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"}, (
        "Set answer_support to SUPPORTED, PARTIALLY_SUPPORTED or UNSUPPORTED."
    )
    for field in ["source_isolation", "grain_correctness"]:
        assert review.get(field) in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}, (
            f"Set {field} to CORRECT, INCORRECT or NOT_EVALUABLE."
        )
    assert review.get("sql_capture_complete") is None or isinstance(review["sql_capture_complete"], bool), (
        "sql_capture_complete must be True, False or None."
    )
    if review.get("sql_capture_complete") is True:
        assert review.get("sql_evidence") and review.get("sql_capture_note", "").strip(), (
            "To mark SQL capture complete, provide the original full query/trace "
            "and explain its completeness in sql_capture_note."
        )
    with evidence_lock():
        state = load_checkpoint()
        trial = state["trials"][review["trial_key"]]
        assert trial["state"] == "RECEIVED", "No complete original response is available."
        assert review["response_fingerprint"] == trial["response_fingerprint"] == fingerprint(trial["response"]), (
            "The saved response changed. Start again from its current template."
        )
        question = trial["question"]
        expected_sections = set(MANIFEST["contracts"][question])
        assert set(review["sections"]) == set(review["aliases"]) == expected_sections, (
            "Keep the template's section names in both sections and aliases."
        )
        assert all(
            isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
            for rows in review["sections"].values()
        ), (
            "Fill each section with a list of row dictionaries. "
            "Use [] only for a confirmed empty result, not missing evidence."
        )
        if any(review["aliases"].values()):
            assert review.get("alias_evidence", "").strip(), (
                "Verify aliases against the recorded SQL/source meaning, not name similarity."
            )
        if question == "C07":
            assert isinstance(review.get("honest_no_match"), bool), (
                "A query error or refusal is not a successful no-match answer."
            )
        if question == "R01":
            assert isinstance(review.get("sources_and_dates_correct"), bool), (
                "Check source names, separate dates and that no customer join was inferred."
            )
        for sql in review["sql_evidence"]:
            assert sql.get("text", "").strip() and sql.get("evidence_note", "").strip(), (
                "Each SQL entry needs its original text and an evidence_note."
            )
            assert sql.get("correctness") in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}, (
                "Each SQL correctness value must be CORRECT, INCORRECT or NOT_EVALUABLE."
            )
            seconds = sql.get("execution_seconds")
            assert seconds is None or (
                isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
                and math.isfinite(seconds) and seconds >= 0
            ), "SQL execution_seconds must be a finite, nonnegative number, or None when unavailable."
            if seconds is not None:
                assert sql.get("timing_evidence", "").strip(), "SQL duration needs query-history/trace evidence."
        history = trial.setdefault("reviews", [])
        cleaned = json.loads(stable_json(review))
        # Append corrections without replacing earlier evidence.
        if not history or history[-1]["review"] != cleaned:
            history.append({"at_utc": utc_now(), "review": cleaned})
            save_checkpoint(state)
    print(f"Answer check recorded: {question} | Agent {trial['arm']} | Repetition {trial['repetition']}.")
    print("Identical entries are left unchanged. No new question was sent.")


print("1. Read the saved answer: show_trial('C01', 'A', 1)")
print("2. Create its record: review = review_template('C01', 'A', 1)")
print("3. Fill review from that answer and its original SQL/trace, then run record_answer_review(review).")
print("   Check all verdicts, including answer_support; template defaults are not findings.")
print("   Use plain numbers; preserve NULL as None. Use [] only for a confirmed empty result.")
print("   Use ISO date/time text at the recorded precision; explain format conversions in evidence_note.")
print("   Leave unavailable SQL, model details and timings as NOT_EVALUABLE/None.")
print("4. Repeat for the other saved answers, then run cell 14 for the report.")
