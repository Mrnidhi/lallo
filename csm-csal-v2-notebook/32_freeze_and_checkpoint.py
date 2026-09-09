# Notebook cell 7 (file 32) | Freeze the approved experiment and retain restart evidence
# Creates one evidence file in the existing personal workspace folder, if enabled.
# This file may contain business rows. Keep it in the approved workspace.

V2_BENCHMARK_READY = False
assert "PREPARATION_STAMPS" in globals() and "questions" in PREPARATION_STAMPS, "Notebook cells 3-6 must complete successfully before freezing."
require_preparation("sources", SOURCE_MARKER)
require_preparation("booking", booking_payload())
require_preparation("shared", ground_truth_payload())
require_preparation("questions", review_payload())
assert REVIEW.get("draft_sha256") == DRAFT_REVIEW_SHA256 == fingerprint(review_payload()), "Approval must name the exact draft fingerprint from notebook cell 6."
assert spark.conf.get("spark.sql.session.timeZone") == SESSION_TIME_ZONE, "Session timezone changed. Recheck the timestamp results."
required_reviews = ["business_logic_and_ground_truth", "source_local_fixtures", "ordering_and_precision", "current_agent_controls", "managed_model_limitation_accepted"]
assert all(REVIEW.get(key) is True for key in required_reviews), "Review notebook cells 3-6 before approving ground truth."
assert REVIEW["reviewer"].strip() and REVIEW["notes"].strip(), "Record who reviewed the business logic and what was checked."
assert CONTROL_EVIDENCE["checked_at_utc"] and all(CONTROL_EVIDENCE[key] is True for key in ["same_shared_readers", "only_csm_reader_differs", "same_warehouse_and_settings"])
assert source_markers() == SOURCE_MARKER, "The approved source state changed. Prepare a new experiment; do not mix runs."

MANIFEST = {
    "label": EXPERIMENT_LABEL, "code_version": CODE_VERSION, "wording_version": WORDING_VERSION,
    "method_version": METHOD_VERSION, "sources": SOURCE_MARKER, "baseline_version": BASELINE_VERSION,
    "original_gold_version": 32, "endpoints": ENDPOINTS, "warehouse": WAREHOUSE_ID,
    "prompts": PROMPTS, "expected": GT, "ground_truth_sql": GT_SQL, "ground_truth_parameters": GT_PARAMETERS,
    "contracts": CONTRACTS, "traceability": TRACEABILITY, "fixtures": {"lookup": LOOKUP_FIXTURE, "sales": SALES_FIXTURES},
    "review": REVIEW, "controls": CONTROL_EVIDENCE, "repetitions": REPETITIONS,
    "session_timezone": SESSION_TIME_ZONE,
    "limitations": ["Underlying managed models and equality are unverified.", "This is not a replica of the custom production supervisor.",
                    "Shared sources are live; version markers detect drift but do not lock the data.",
                    "Only 12 of the 41 proposed questions are in this batch.", "Enrichment, threshold calibration and swap scoring remain deferred."],
}
# Round-trip into JSON-safe values so resuming preserves the same fingerprint.
MANIFEST = json.loads(stable_json(MANIFEST))
EXPERIMENT_ID = fingerprint(MANIFEST)


def trial_id(qid, arm, repetition):
    return fingerprint([EXPERIMENT_ID, qid, arm, repetition])


PLAN = []
for repetition in range(1, REPETITIONS + 1):
    for number, qid in enumerate(QUESTION_IDS):
        # Alternate which arm goes first; keep each question/repetition paired.
        arms = ["A", "B"] if (number + repetition) % 2 else ["B", "A"]
        for arm in arms:
            PLAN.append({"trial_id": trial_id(qid, arm, repetition), "question": qid, "arm": arm, "repetition": repetition})
assert len(PLAN) == len({item["trial_id"] for item in PLAN}) == 72


def validate_evidence_path():
    expected_parent = Path("/Workspace/Users/" + PERSONAL_OWNER + "/Sales AI EDA")
    assert EVIDENCE_PATH.parent == expected_parent and EVIDENCE_PATH.name == "v2-benchmark-evidence.json"
    assert expected_parent.is_dir(), "Personal workspace files are unavailable. Stop; do not use another destination."
    assert not EVIDENCE_PATH.is_symlink(), "Unexpected evidence-file symlink."


def save_checkpoint(state):
    assert ENABLE_EVIDENCE_SAVE is True, "Enable only the personal evidence-file save before running."
    validate_evidence_path()
    payload = stable_json(state)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".v2-evidence-", dir=str(EVIDENCE_PATH.parent), delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(EVIDENCE_PATH))
        assert EVIDENCE_PATH.read_text(encoding="utf-8") == payload, "Evidence read-back failed. Stop before another request."
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if ENABLE_EVIDENCE_SAVE:
    validate_evidence_path()
    if EVIDENCE_PATH.exists():
        STATE = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        assert STATE["experiment_id"] == EXPERIMENT_ID and STATE["manifest"] == MANIFEST, "Existing evidence belongs to a different experiment. Preserve it and review."
        assert STATE["plan"] == PLAN, "Saved trial plan differs."
        print("Existing experiment loaded. Completed or uncertain trials will not be resubmitted.")
    else:
        STATE = {"experiment_id": EXPERIMENT_ID, "manifest": MANIFEST, "plan": PLAN, "trials": {}, "created_at_utc": utc_now()}
        # An existing file is never deliberately reset to an empty ledger.
        lock = EVIDENCE_PATH.with_suffix(".lock")
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            assert not EVIDENCE_PATH.exists(), "Another process created the evidence file. Stop."
            save_checkpoint(STATE)
        finally:
            os.close(fd)
            lock.unlink()
        print("Personal evidence file created and read back.")
    V2_BENCHMARK_READY = True
else:
    print("Approved manifest prepared in memory. File saving and agent runs are still disabled.")
print("This does not submit any agent question.")
