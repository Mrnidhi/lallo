# Cell 7 | Save the test setup
# Save one checkpoint in the personal workspace so the same test can resume.
# It can contain business rows and must stay in that workspace.

V2_BENCHMARK_READY = False


assert "PREPARATION_STAMPS" in globals() and "questions" in PREPARATION_STAMPS, "Notebook cells 3-6 must complete successfully before freezing."
require_preparation("sources", SOURCE_MARKER)
require_preparation("booking", booking_payload())
require_preparation("shared", ground_truth_payload())
require_preparation("questions", review_payload())
assert DRAFT_REVIEW_SHA256 == fingerprint(review_payload()), "Reference answers changed. Repeat cells 3-6 before saving."
assert spark.conf.get("spark.sql.session.timeZone") == SESSION_TIME_ZONE, "Session timezone changed. Recheck the timestamp results."
assert source_markers() == SOURCE_MARKER, "Source data changed since preparation. Keep existing evidence separate and prepare the reference answers again."

MANIFEST = {
    "label": EXPERIMENT_LABEL, "code_version": CODE_VERSION, "wording_version": WORDING_VERSION,
    "method_version": METHOD_VERSION, "sources": SOURCE_MARKER, "baseline_version": BASELINE_VERSION,
    "original_gold_version": 32, "endpoints": ENDPOINTS, "warehouse": WAREHOUSE_ID,
    "prompts": PROMPTS, "expected": GT, "ground_truth_sql": GT_SQL, "ground_truth_parameters": GT_PARAMETERS,
    "routing_contract": ROUTING_CONTRACT,
    "contracts": CONTRACTS, "traceability": TRACEABILITY, "fixtures": {"lookup": LOOKUP_FIXTURE, "sales": SALES_FIXTURES},
    "reference_sha256": DRAFT_REVIEW_SHA256, "repetitions": REPETITIONS,
    "reference_status": "CALCULATIONS_CROSS_CHECKED_NOT_BUSINESS_SIGNED_OFF",
    "session_timezone": SESSION_TIME_ZONE,
    "experiment_note": "New routing-contract experiment. Earlier C01 client2 attempts remain in their original evidence file; they are not reconciled, copied or erased by this run.",
    "limitations": ["Underlying managed models and equality are unverified.", "This is not a replica of the custom production supervisor.",
                    "Shared sources are live; version markers detect drift but do not lock the data.",
                    "The warehouse ID is the intended setting, not proof of actual per-request warehouse use.",
                    "The supervisor routing contract was manually read back before this experiment; this notebook does not independently fetch the saved UI configuration.",
                    "Agreement with reference SQL does not independently certify business policy.",
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
assert len(PLAN) == len({item["trial_id"] for item in PLAN}) == len(QUESTION_IDS) * len(ENDPOINTS) * REPETITIONS


def validate_evidence_path():
    expected_parent = Path("/Workspace/Users/" + PERSONAL_OWNER + "/Sales AI EDA")
    assert EVIDENCE_PATH.parent == expected_parent and EVIDENCE_PATH.name == "v2-benchmark-routing1-evidence.json"
    assert expected_parent.is_dir(), "Personal workspace files are unavailable. Stop; do not use another destination."
    assert not EVIDENCE_PATH.is_symlink(), "Unexpected evidence-file symlink."


def save_checkpoint(state):
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


validate_evidence_path()
# Use the same lock for creation and resuming. Never replace an old experiment.
lock = EVIDENCE_PATH.with_suffix(".lock")
fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
try:
    if EVIDENCE_PATH.exists():
        STATE = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        assert STATE["experiment_id"] == EXPERIMENT_ID and STATE["manifest"] == MANIFEST, "An existing checkpoint has different test settings. Keep it unchanged; do not overwrite or delete it."
        assert STATE["plan"] == PLAN, "Saved trial plan differs."
        print("Existing experiment loaded. Completed or uncertain trials will not be resubmitted.")
    else:
        STATE = {"experiment_id": EXPERIMENT_ID, "manifest": MANIFEST, "plan": PLAN, "trials": {}, "created_at_utc": utc_now()}
        save_checkpoint(STATE)
        print("Personal evidence file created and read back.")
    V2_BENCHMARK_READY = True
finally:
    os.close(fd)
    lock.unlink()
print("Setup saved. Next: run cells 8-11. No agent question was sent.")
