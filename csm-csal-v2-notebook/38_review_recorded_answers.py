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
    """Save answer evidence, including unfinished checks, without replacing history."""
    assert isinstance(review, dict), "Pass the completed dictionary returned by review_template()."
    assert review.get("reviewer", "").strip() and review.get("evidence_note", "").strip(), (
        "Fill reviewer and evidence_note with who checked the answer and what supports it."
    )
    assert review.get("narrative_correct") is None or isinstance(review["narrative_correct"], bool), (
        "Use True or False after checking the claims and qualifications; otherwise leave narrative_correct as None."
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
            assert review.get("honest_no_match") is None or isinstance(review["honest_no_match"], bool), (
                "Leave honest_no_match as None until checked. A query error or refusal is not a successful no-match answer."
            )
        if question == "R01":
            assert review.get("sources_and_dates_correct") is None or isinstance(review["sources_and_dates_correct"], bool), (
                "Leave sources_and_dates_correct as None until source names, separate dates and customer separation are checked."
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
    print(f"Answer evidence recorded: {question} | Agent {trial['arm']} | Repetition {trial['repetition']}.")
    print("Identical entries are left unchanged. No new question was sent.")


def record_answer(question, arm, repetition, rows, *, note, narrative_correct=None,
                  sql=None, honest_no_match=None, sources_and_dates_correct=None):
    """Save original row lists; R01 uses a dictionary of its two section lists.

    note identifies the saved response/SQL. Optional verdicts stay unknown;
    SQL text alone does not establish correctness, completeness, source or grain.
    """
    assert globals().get("V2_BENCHMARK_READY") is True, "Run cell 7 to load the saved test setup first."
    assert question in QUESTION_IDS and arm in ENDPOINTS and type(repetition) is int and 1 <= repetition <= REPETITIONS, (
        "Choose a listed question, arm A or B, and a planned repetition."
    )
    assert isinstance(note, str) and note.strip(), "Add a short note identifying the original response used."
    assert isinstance(PERSONAL_OWNER, str) and PERSONAL_OWNER.strip(), "The notebook identity is missing. Run the source checks first."
    for name, value in [("narrative_correct", narrative_correct), ("honest_no_match", honest_no_match),
                        ("sources_and_dates_correct", sources_and_dates_correct)]:
        assert value is None or type(value) is bool, name + " must be True, False or None."
    assert sql is None or isinstance(sql, str) and sql.strip(), "Supply original SQL text, or leave sql as None."

    review = review_template(question, arm, repetition)
    section_names = set(review["sections"])
    if isinstance(rows, list):
        assert len(section_names) == 1, "This question has separate sections. Supply a dictionary with their original row lists."
        sections = {next(iter(section_names)): rows}
    else:
        assert isinstance(rows, dict) and set(rows) == section_names, (
            "Supply the original row lists under exactly these sections: " + ", ".join(sorted(section_names))
        )
        sections = rows
    review.update(reviewer=PERSONAL_OWNER, evidence_note=note, sections=sections,
                  narrative_correct=narrative_correct, honest_no_match=honest_no_match,
                  sources_and_dates_correct=sources_and_dates_correct)
    if sql is not None:
        review["sql_evidence"] = [{"text": sql, "evidence_note": note,
                                   "correctness": "NOT_EVALUABLE", "execution_seconds": None}]
    record_answer_review(review)
    print("Rows can now be compared. Unchecked claims, SQL, sources and grain remain unavailable.")
    return review["trial_key"]


print("Read show_trial('C01', 'A', 1), then copy its original rows into actual_rows, never from the reference.")
print("record_answer('C01', 'A', 1, actual_rows, note='Copied from the saved C01 A response')")
print("Optional checked claims: narrative_correct; C07: honest_no_match; R01: sources_and_dates_correct. Leave unknown as None.")
print("R01 rows: {'booking': booking_rows, 'finance': finance_rows}. Optional SQL: sql=original_sql; no SQL verdict is inferred.")
print("Keep NULL as None, [] only for genuine empty results, and original date/time precision. Explain conversions in note.")
print("Detailed checks still use review_template() and record_answer_review(). Next: cell 14. No new question is sent here.")
print("Full target: 41 questions. This batch has 12 prepared questions; the other 29 remain pending.")
