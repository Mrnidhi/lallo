# Cell 13 | Record the actual answers
# The first saved C01 pair is parsed and recorded only when it has no review yet.
# Existing reviews are retained. Expected answers are never used as actual rows.


def inspect_saved_answers(question="C01", repetition=1):
    """Display original saved answers and tool records without sending a request."""
    assert V2_BENCHMARK_READY, "Load the saved experiment before inspecting answers."
    assert question in QUESTION_IDS and type(repetition) is int and 1 <= repetition <= REPETITIONS
    saved = load_checkpoint()

    def show_value(value):
        print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    print("Required output columns:", MANIFEST["contracts"][question])
    for arm in ("A", "B"):
        print(f"\n{question} | Agent {arm} | Repetition {repetition}")
        trial = saved["trials"].get(trial_id(question, arm, repetition))
        if trial is None:
            print("No saved response for this selection.")
            continue
        print("State:", trial["state"], "| Source check:", trial.get("source_check"))
        print("Agent response status:", trial.get("response_status") or "not supplied")
        response = trial.get("response")
        if response is None:
            print("No complete response was saved. Do not resend this request.")
            continue
        assert trial.get("response_fingerprint") == fingerprint(response), "Saved response changed."
        items = response.get("output", [])
        if not isinstance(items, list):
            show_value(items)
            continue
        for index, item in enumerate(items, 1):
            if not isinstance(item, dict):
                print("Output item:", index)
                show_value(item)
                continue
            print("\nOutput item:", index, "|", {key: item.get(key) for key in ("type", "name", "call_id", "role")})
            if item.get("type") == "message":
                content = item.get("content", [])
                for part in content if isinstance(content, list) else [content]:
                    show_value(part.get("text", part) if isinstance(part, dict) else part)
            elif item.get("type") == "function_call":
                show_value(item.get("arguments"))
            elif item.get("type") == "function_call_output":
                show_value(item.get("output"))
            else:
                show_value(item)


def _saved_c01_rows(trial, required_headers):
    """Read the one final-answer table, without consulting reference answers."""
    assert trial["state"] == "RECEIVED" and not trial.get("response_problem"), "A complete saved response is required."
    response = trial["response"]
    assert trial["response_fingerprint"] == fingerprint(response), "Saved response changed."
    outputs = response.get("output")
    assert isinstance(outputs, list) and outputs, "No saved output items."
    final = outputs[-1]
    assert isinstance(final, dict) and final.get("type") == "message" and final.get("role") == "assistant" and not final.get("call_id"), "The last item is not the final assistant message."
    content = final.get("content")
    assert isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict), "Expected one final text block."
    text = content[0].get("text")
    assert content[0].get("type") == "output_text" and isinstance(text, str), "Final answer is not plain text."
    lines = text.splitlines()
    positions = [index for index, line in enumerate(lines) if line.strip().startswith("|") or line.strip().endswith("|")]
    assert len(positions) >= 3 and positions == list(range(positions[0], positions[-1] + 1)), "Expected one contiguous answer table."
    table = [lines[index].strip() for index in positions]
    assert all(line.startswith("|") and line.endswith("|") and "\\|" not in line for line in table), "Malformed or escaped table delimiter."
    cells = [[value.strip() for value in line[1:-1].split("|")] for line in table]
    headers = cells[0]
    assert all(headers) and len(set(headers)) == len(headers) and set(required_headers).issubset(headers), "Required headers are missing or duplicated."
    assert all(len(row) == len(headers) for row in cells), "Table widths differ."
    assert all(re.fullmatch(r":?-{3,}:?", value) for value in cells[1]), "Invalid Markdown separator."
    assert all(value for row in cells[2:] for value in row), "Empty cells are ambiguous; inspect the original."
    return [dict(zip(headers, row)) for row in cells[2:]]


def compare_saved_c01():
    """Preview saved C01 row comparisons only; no evidence or verdict is written."""
    aliases = dict(zip(["customer", "agreement", "tcr", "confirmed_teu", "total_reviewed_teu", "fulfillment_pct"],
                       ["Customer", "Agreement", "TCR", "Confirmed TEU", "Total Reviewed Commitment", "Utilization %"]))
    saved = load_checkpoint()
    actual = {arm: _saved_c01_rows(saved["trials"][trial_id("C01", arm, 1)], aliases.values()) for arm in ("A", "B")}
    # Extraction above never reads the reference. Use it only for this comparison.
    reference = MANIFEST["expected"]["C01"]["answer"]
    contract = MANIFEST["contracts"]["C01"]["answer"]
    reference_keys = Counter(tuple(row[key] for key in ("customer", "agreement", "tcr")) for row in reference)
    scores = {}
    for arm, rows in actual.items():
        scores[arm] = score_section(reference, rows, contract["columns"], contract["precision"], aliases, ordered=True)
        actual_keys = Counter(tuple(row[aliases[key]] for key in ("customer", "agreement", "tcr")) for row in rows)
        matching_keys = sum((reference_keys & actual_keys).values())
        consistent, checked = 0, 0
        for row in rows:
            try:
                confirmed, reviewed, percentage = [_v2_decimal(row[aliases[key]]) for key in ("confirmed_teu", "total_reviewed_teu", "fulfillment_pct")]
                if reviewed <= 0:
                    continue
                calculated = confirmed / reviewed * Decimal(100)
                consistent += _v2_decimal_token(calculated, 6) == _v2_decimal_token(percentage, 6)
                checked += 1
            except (ValueError, InvalidOperation, OverflowError):
                continue
        print(arm, {"rows": len(rows), "row_status": scores[arm]["status"], "display_header_contract": scores[arm]["contract_compliant"],
                    "matching_keys": matching_keys, "ratio_consistent": consistent, "ratio_checked": checked, "ratio_unchecked": len(rows) - checked})
    return {"rows": actual, "scores": scores, "aliases": aliases,
            "alias_note": "Display labels mapped to the C01 question's defined fields; SQL and source usage remain unverified."}


def show_trial(question, arm, repetition=1):
    """Read one saved response without asking the agent again."""
    state = load_checkpoint()
    key = trial_id(question, arm, repetition)
    assert key in state["trials"], "This question has not been sent in this experiment."
    trial = state["trials"][key]
    print(f"{question} | Agent {arm} | Repetition {repetition}")
    print("State:", trial["state"], "| Source check:", trial.get("source_check"))
    print("Agent response status:", trial.get("response_status") or "not supplied")
    print(stable_json(trial.get("response")))
    return key


def record_answer(question, arm, repetition, rows, *, note,
                  narrative_correct=None, honest_no_match=None,
                  sources_and_dates_correct=None, sql=None,
                  source_isolation="NOT_EVALUABLE", grain_correctness="NOT_EVALUABLE",
                  answer_support="SUPPORTED", aliases=None, alias_note="",
                  sql_capture_complete=None, sql_capture_note="", only_if_unreviewed=False):
    """Save copied rows and optional evidence. Unknown checks stay unknown.

    For most questions rows is a list of dictionaries. R01 has two lists:
    {"booking": booking_rows, "finance": finance_rows}.
    sql can be original SQL text or a list of SQL evidence dictionaries.
    """
    assert V2_BENCHMARK_READY, "Load this experiment before recording answers."
    assert question in QUESTION_IDS and arm in ENDPOINTS
    assert type(repetition) is int and 1 <= repetition <= REPETITIONS
    assert isinstance(note, str) and note.strip(), "Identify the original response used."
    assert type(only_if_unreviewed) is bool
    assert answer_support in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"}
    for value in (narrative_correct, honest_no_match, sources_and_dates_correct, sql_capture_complete):
        assert value is None or type(value) is bool, "Use True, False or None for an unchecked claim."
    for value in (source_isolation, grain_correctness):
        assert value in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}

    sections = {"answer": rows} if isinstance(rows, list) else rows
    section_names = set(MANIFEST["contracts"][question])
    assert isinstance(sections, dict) and set(sections) == section_names
    assert all(isinstance(values, list) and all(isinstance(row, dict) for row in values)
               for values in sections.values()), "Use [] only for an actual empty result."
    aliases = {name: {} for name in section_names} if aliases is None else aliases
    assert set(aliases) == section_names and all(isinstance(value, dict) for value in aliases.values())
    assert not any(aliases.values()) or alias_note.strip(), "Explain how the SQL/source meaning verifies each alias."

    if isinstance(sql, str):
        assert sql.strip(), "Supply original SQL text or leave sql as None."
        sql = [{"text": sql, "evidence_note": note,
                "correctness": "NOT_EVALUABLE", "execution_seconds": None}]
    sql_evidence = [] if sql is None else sql
    assert isinstance(sql_evidence, list)
    for entry in sql_evidence:
        assert isinstance(entry, dict) and entry.get("text", "").strip()
        assert entry.get("evidence_note", "").strip(), "Identify the saved query or trace."
        assert entry.get("correctness") in {"CORRECT", "INCORRECT", "NOT_EVALUABLE"}
        seconds = entry.get("execution_seconds")
        assert seconds is None or (type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0)
        assert seconds is None or entry.get("timing_evidence", "").strip(), "SQL timing needs query-history evidence."
    assert sql_capture_complete is not True or (sql_evidence and sql_capture_note.strip()), (
        "A complete SQL capture needs its original statements and a note identifying the full trace."
    )

    with evidence_lock():
        state = load_checkpoint()
        key = trial_id(question, arm, repetition)
        trial = state["trials"].get(key)
        assert trial and trial["state"] == "RECEIVED", "No complete response was saved."
        assert trial["response_fingerprint"] == fingerprint(trial["response"]), "Saved response changed."
        assert not trial.get("response_problem"), "This reply is unfinished or contains an error."
        if only_if_unreviewed and trial.get("reviews"):
            print(f"Existing answer evidence retained: {question} | Agent {arm} | Repetition {repetition}.")
            return key
        review = {
            "trial_key": key, "response_fingerprint": trial["response_fingerprint"],
            "reviewer": PERSONAL_OWNER, "evidence_note": note, "sections": sections,
            "aliases": aliases, "alias_evidence": alias_note, "answer_support": answer_support,
            "narrative_correct": narrative_correct, "honest_no_match": honest_no_match,
            "sources_and_dates_correct": sources_and_dates_correct,
            "source_isolation": source_isolation, "grain_correctness": grain_correctness,
            "sql_evidence": sql_evidence, "sql_capture_complete": sql_capture_complete,
            "sql_capture_note": sql_capture_note,
        }
        review = json.loads(stable_json(review))
        history = trial.setdefault("reviews", [])
        if not history or history[-1]["review"] != review:
            history.append({"at_utc": utc_now(), "review": review})
            save_checkpoint(state)
    print(f"Saved answer evidence: {question} | Agent {arm} | Repetition {repetition}.")
    return key


print("The first saved C01 pair is inspected below; only previously unreviewed answers are recorded.")
print("For later questions, use show_trial and record_answer with their original returned rows.")
print("Set narrative_correct=True only after checking the answer's claims.")
print("Missing SQL, source and grain checks remain unavailable. Cell 14 shows the comparison.")


if globals().get("V2_BENCHMARK_READY") is True and callable(globals().get("load_checkpoint")):
    inspection_trials = load_checkpoint()["trials"]
    if all(trial_id("C01", arm, 1) in inspection_trials for arm in ("A", "B")):
        inspect_saved_answers()
        C01_COMPARISON = compare_saved_c01()
        initial_note = ("Parsed the original saved C01 final Markdown table. Only outer cell padding was trimmed; "
                        "values, rows, order and headers were preserved. Reader routing and SQL checks are recorded separately.")
        for arm in ("A", "B"):
            record_answer("C01", arm, 1, C01_COMPARISON["rows"][arm], note=initial_note,
                          aliases={"answer": C01_COMPARISON["aliases"]}, alias_note=C01_COMPARISON["alias_note"],
                          narrative_correct=None, source_isolation="NOT_EVALUABLE",
                          grain_correctness="NOT_EVALUABLE", sql=None, only_if_unreviewed=True)
    else:
        print("No saved C01 A/B pair is available for inspection.")
