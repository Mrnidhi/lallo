# Optional diagnostic. Paste into a temporary Python cell at the notebook's end.
# Reads existing variables only. No queries, files, approvals or agent calls.


def show_cell_7_checks():
    notebook_state = globals()

    def stored_mapping(name):
        value = notebook_state.get(name)
        return value if isinstance(value, dict) else {}

    def has_text(value):
        return isinstance(value, str) and bool(value.strip())

    def flag_label(value):
        if value is True:
            return "TRUE recorded (still needs supporting evidence)"
        if value is False or value is None:
            return "PENDING: False or not set"
        return "INVALID: use a Boolean only after the review"

    preparation = stored_mapping("PREPARATION_STAMPS")
    review = stored_mapping("REVIEW")
    controls = stored_mapping("CONTROL_EVIDENCE")

    print("CELL 7 CHECK | Read-only status")
    print("\n1. Earlier preparation")
    for stage in ("sources", "booking", "shared", "questions"):
        recorded = isinstance(preparation.get(stage), dict) and bool(preparation[stage])
        print(stage + ": " + ("receipt present; freshness not checked here" if recorded else "MISSING receipt"))

    print("\n2. Required review flags")
    for name in (
        "business_logic_and_ground_truth",
        "source_local_fixtures",
        "ordering_and_precision",
        "current_agent_controls",
        "managed_model_limitation_accepted",
    ):
        print(name + ": " + flag_label(review.get(name)))

    print("\n3. Review record")
    for name in ("reviewer", "notes"):
        print(name + ": " + ("provided; contents not displayed" if has_text(review.get(name)) else "MISSING"))

    draft = notebook_state.get("DRAFT_REVIEW_SHA256")
    approved_draft = review.get("draft_sha256")
    if not has_text(draft):
        print("draft reference: MISSING cell 6 fingerprint")
    elif not has_text(approved_draft):
        print("draft reference: MISSING approval fingerprint")
    elif approved_draft != draft:
        print("draft reference: MISMATCH; review the current draft before approving it")
    else:
        print("draft reference: matches the stored cell 6 fingerprint; not revalidated here")

    print("\n4. Current agent-control record")
    for name in ("same_shared_readers", "only_csm_reader_differs", "same_warehouse_and_settings"):
        print(name + ": " + flag_label(controls.get(name)))
    print("checked_at_utc: " + ("provided; actual verification date not checked" if has_text(controls.get("checked_at_utc")) else "MISSING"))

    print("\n5. Execution switches (not changed)")
    for name in ("ENABLE_EVIDENCE_SAVE", "ENABLE_AGENT_RUNS", "V2_BENCHMARK_READY"):
        value = notebook_state.get(name)
        label = "True" if value is True else "False" if value is False else "NOT SET or invalid"
        print(name + ": " + label)

    print("\nNo review flags or existing notebook values were changed.")
    print("This is not approval or a readiness test. Live sources, timezone and saved files were not checked.")
    print("Keep agent runs off while resolving the original error. Do not change a flag just to clear it.")
    print("Share this status output. Also provide only the AssertionError text and failing code line, with private details removed.")


show_cell_7_checks()
