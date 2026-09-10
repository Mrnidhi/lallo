# Cell 18 | Review saved CSM answers
# Reads answers already stored in the checkpoint. It never asks an agent.
# Header matching is exact and deliberately stops on unfamiliar wording.

assert callable(globals().get("csm_load_checkpoint")), "Load the CSM checkpoint first."
assert callable(globals().get("_saved_c01_rows")), "Load the saved-answer review cell first."
assert callable(globals().get("record_answer"))

CSM_HEADER_NAMES = {
    "customer": ["customer", "Customer", "Customer Name"],
    "agreement": ["agreement", "Agreement", "Agreement Number"],
    "tcr": ["tcr", "TCR"],
    "confirmed_teu": ["confirmed_teu", "Confirmed TEU"],
    "cancelled_teu": ["cancelled_teu", "Cancelled TEU", "Canceled TEU"],
    "rejected_teu": ["rejected_teu", "Rejected TEU"],
    "pended_teu": ["pended_teu", "Pended TEU"],
    "terminated_teu": ["terminated_teu", "Terminated TEU"],
    "no_show_teu": ["no_show_teu", "No-show TEU", "No Show TEU"],
    "booked_teu": ["booked_teu", "Booked TEU", "Total Booked TEU"],
    "total_reviewed_teu": [
        "total_reviewed_teu",
        "Total Reviewed TEU",
        "Total Reviewed Commitment",
        "Total Reviewed Commitment TEU",
    ],
    "fulfillment_pct": [
        "fulfillment_pct",
        "Fulfillment %",
        "Utilization %",
        "Confirmed Utilization %",
    ],
    "cancellation_pct": [
        "cancellation_pct",
        "Cancellation %",
        "Cancellation Percentage",
    ],
    "rejection_pct": ["rejection_pct", "Rejection %", "Rejection Percentage"],
    "booking_pct": ["booking_pct", "Booking %", "Booking Utilization", "Booking Utilization %"],
}


def final_answer_text(trial):
    response = trial.get("response")
    assert isinstance(response, dict), "The saved response is unavailable."
    assert trial.get("response_fingerprint") == fingerprint(response), "The saved response changed."
    outputs = response.get("output")
    assert isinstance(outputs, list) and outputs, "The response has no output items."
    final = outputs[-1]
    assert isinstance(final, dict) and final.get("type") == "message", (
        "The final output is not a message. Inspect it with show_trial."
    )
    content = final.get("content")
    assert isinstance(content, list) and len(content) == 1
    text = content[0].get("text") if isinstance(content[0], dict) else None
    assert isinstance(text, str) and text.strip(), "The final answer has no plain text."
    return text


def exact_header_map(question, rows):
    required = MANIFEST["contracts"][question]["answer"]["columns"]
    headers = list(rows[0]) if rows else []
    mapping = {}
    for canonical in required:
        allowed = CSM_HEADER_NAMES.get(canonical, [canonical])
        matches = [header for header in headers if header in allowed]
        assert len(matches) == 1, (
            f"Cannot prove the {canonical!r} header. Found {matches}; table headers are {headers}."
        )
        if matches[0] != canonical:
            mapping[canonical] = matches[0]
    used_headers = {mapping.get(name, name) for name in required}
    assert used_headers == set(headers), (
        "The answer contains extra or missing columns. Inspect it before recording."
    )
    return mapping


def preview_csm_answer(question, arm, repetition=1):
    assert question in QUESTION_IDS and arm in ("A", "B")
    state = csm_load_checkpoint()
    key = trial_id(question, arm, repetition)
    trial = state["trials"].get(key)
    assert trial and trial.get("state") == "RECEIVED", "No complete saved response exists for this run."
    assert not trial.get("response_problem"), "The saved response is incomplete."

    text = final_answer_text(trial)
    print(f"{question} | Agent {arm} | Repetition {repetition}")
    if question == "C07":
        print(text)
        print("C07 must be recorded only after confirming that this exact customer has no match.")
        return {"question": question, "arm": arm, "repetition": repetition, "text": text}

    rows = _saved_c01_rows(trial, [])
    aliases = exact_header_map(question, rows)
    contract = MANIFEST["contracts"][question]["answer"]
    provisional = score_section(
        MANIFEST["expected"][question]["answer"],
        rows,
        contract["columns"],
        contract["precision"],
        aliases,
        ordered=True,
    )
    print("Rows:", len(rows))
    print("Exact header mapping:", aliases or "canonical headers")
    print("Provisional row comparison:", provisional["status"])
    print("Read the original answer before recording its narrative, source, grain or SQL checks.")
    return {
        "question": question,
        "arm": arm,
        "repetition": repetition,
        "rows": rows,
        "aliases": aliases,
        "row_comparison": provisional,
        "text": text,
    }


def record_verified_csm_table(
    question,
    arm,
    repetition,
    *,
    narrative_correct,
    source_isolation="NOT_EVALUABLE",
    grain_correctness="NOT_EVALUABLE",
    sql=None,
    sql_capture_complete=None,
    sql_capture_note="",
):
    assert question in QUESTION_IDS and question != "C07"
    assert type(narrative_correct) is bool, "Confirm whether the answer's written claims are correct."
    preview = preview_csm_answer(question, arm, repetition)
    alias_note = ""
    if preview["aliases"]:
        alias_note = "Each friendly header was matched through the exact CSM header allowlist in cell 18."
    return record_answer(
        question,
        arm,
        repetition,
        preview["rows"],
        note="Recorded from the original final Markdown table saved for this trial.",
        narrative_correct=narrative_correct,
        source_isolation=source_isolation,
        grain_correctness=grain_correctness,
        sql=sql,
        aliases={"answer": preview["aliases"]},
        alias_note=alias_note,
        sql_capture_complete=sql_capture_complete,
        sql_capture_note=sql_capture_note,
        only_if_unreviewed=True,
    )


def record_verified_csm_no_match(
    arm,
    repetition,
    *,
    exact_no_match_confirmed,
    source_isolation="NOT_EVALUABLE",
    grain_correctness="NOT_EVALUABLE",
    sql=None,
    sql_capture_complete=None,
    sql_capture_note="",
):
    assert exact_no_match_confirmed is True, (
        "Read the saved C07 answer first and confirm the exact customer was not replaced."
    )
    preview_csm_answer("C07", arm, repetition)
    return record_answer(
        "C07",
        arm,
        repetition,
        [],
        note="The original saved answer explicitly confirmed no match for the exact requested customer.",
        narrative_correct=True,
        honest_no_match=True,
        source_isolation=source_isolation,
        grain_correctness=grain_correctness,
        sql=sql,
        sql_capture_complete=sql_capture_complete,
        sql_capture_note=sql_capture_note,
        only_if_unreviewed=True,
    )


unreviewed = []
for item in PLAN:
    trial = csm_load_checkpoint()["trials"].get(item["trial_id"])
    if trial and trial.get("state") == "RECEIVED" and not trial.get("reviews"):
        unreviewed.append((item["question"], item["arm"], item["repetition"]))
print("Saved CSM answers waiting for review:", unreviewed or "none")
print("Use preview_csm_answer(question, arm, repetition) before recording a saved answer.")
