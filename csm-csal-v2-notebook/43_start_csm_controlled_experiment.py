# Cell 15 | Start the CSM-only controlled experiment
# Derives a new, separate checkpoint from the saved routing1 manifest.
# Read-only setup: no tables, views, agents or production objects are changed.

assert "EVIDENCE_PATH" in globals() and "Path" in globals()
ROUTING1_EVIDENCE_PATH = EVIDENCE_PATH
CSM_EVIDENCE_PATH = ROUTING1_EVIDENCE_PATH.with_name("v2-benchmark-csm-controlled-evidence.json")
CSM_LABEL = "sales_ai_v2_csm_controlled_01"
CSM_CODE_VERSION = "v2_csm_controlled_2026-09-10"
CSM_QUESTION_IDS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]

assert ROUTING1_EVIDENCE_PATH.exists(), "The saved routing1 checkpoint is required."
base_state = json.loads(ROUTING1_EVIDENCE_PATH.read_text(encoding="utf-8"))
base_manifest = base_state["manifest"]
assert fingerprint(base_manifest) == base_state["experiment_id"], (
    "The saved routing1 manifest fingerprint is invalid."
)
assert set(CSM_QUESTION_IDS) <= set(base_manifest["prompts"])

csm_names = set(CSM_DEPENDENCIES)
csm_sources = {
    name: dict(value, format="delta")
    for name, value in base_manifest["sources"]["tables"].items()
    if name in csm_names
}
assert csm_names <= set(csm_sources), "The routing manifest lacks a CSM source marker."
csm_marker = {"tables": csm_sources, "booking_view_sha256": base_manifest["sources"]["booking_view_sha256"]}
current_tables = {}
for name in sorted(csm_names):
    detail = spark.sql("DESCRIBE DETAIL " + name).select("id", "format").first()
    assert detail["format"].lower() == "delta"
    history = spark.sql("DESCRIBE HISTORY " + name).select("version").orderBy(F.desc("version")).first()
    current_tables[name] = {
        "id": detail["id"],
        "version": int(history["version"]),
        "schema_sha256": fingerprint(spark.table(name).schema.jsonValue()),
        "format": detail["format"].lower(),
    }
current_view_hash = fingerprint(spark.sql("SHOW CREATE TABLE " + BOOKING_VIEW).first()[0])
assert {"tables": current_tables, "booking_view_sha256": current_view_hash} == csm_marker, "CSM sources changed; stop before creating evidence."

def csm_subset(mapping):
    return {key: mapping[key] for key in CSM_QUESTION_IDS}

MANIFEST = {
    "label": CSM_LABEL, "code_version": CSM_CODE_VERSION,
    "wording_version": base_manifest["wording_version"], "method_version": base_manifest["method_version"],
    "sources": csm_marker, "baseline_version": base_manifest["baseline_version"],
    "original_gold_version": base_manifest["original_gold_version"], "endpoints": base_manifest["endpoints"],
    "warehouse": base_manifest["warehouse"], "prompts": csm_subset(base_manifest["prompts"]),
    "expected": csm_subset(base_manifest["expected"]), "ground_truth_sql": csm_subset(base_manifest["ground_truth_sql"]),
    "ground_truth_parameters": csm_subset(base_manifest["ground_truth_parameters"]),
    "routing_contract": base_manifest["routing_contract"], "contracts": csm_subset(base_manifest["contracts"]),
    "traceability": {key: value for key, value in base_manifest["traceability"].items() if key in CSM_QUESTION_IDS},
    "fixtures": {"lookup": base_manifest["fixtures"]["lookup"]}, "reference_sha256": None,
    "repetitions": 3, "reference_status": "CALCULATIONS_CROSS_CHECKED_NOT_BUSINESS_SIGNED_OFF",
    "session_timezone": base_manifest["session_timezone"],
    "experiment_note": "Separate CSM-only controlled experiment derived from routing1; prior evidence is unchanged.",
}
QUESTION_IDS = CSM_QUESTION_IDS
SOURCE_MARKER = csm_marker
PROMPTS = MANIFEST["prompts"]
GT = MANIFEST["expected"]
GT_SQL = MANIFEST["ground_truth_sql"]
GT_PARAMETERS = MANIFEST["ground_truth_parameters"]
CONTRACTS = MANIFEST["contracts"]
TRACEABILITY = MANIFEST["traceability"]
METHOD_VERSION = MANIFEST["method_version"]
REPETITIONS = MANIFEST["repetitions"]

def csm_reference_payload():
    return {
        "ground_truth": {"expected": GT, "sql": GT_SQL, "parameters": GT_PARAMETERS,
                         "contracts": CONTRACTS, "lookup": MANIFEST["fixtures"]["lookup"],
                         "source_state": SOURCE_MARKER},
        "prompts": PROMPTS, "traceability": TRACEABILITY,
        "method_version": METHOD_VERSION,
        "inputs": {"label": CSM_LABEL},
    }

MANIFEST["reference_sha256"] = fingerprint(csm_reference_payload())
DRAFT_REVIEW_SHA256 = MANIFEST["reference_sha256"]
LOOKUP_FIXTURE = MANIFEST["fixtures"]["lookup"]
EXPERIMENT_ID = fingerprint(MANIFEST)
PLAN = [{"trial_id": fingerprint([EXPERIMENT_ID, q, arm, rep]), "question": q, "arm": arm, "repetition": rep}
         for rep in range(1, 4) for q in CSM_QUESTION_IDS for arm in (["A", "B"] if (CSM_QUESTION_IDS.index(q) + rep) % 2 else ["B", "A"])]
assert len(PLAN) == len(CSM_QUESTION_IDS) * 2 * 3

EVIDENCE_PATH = CSM_EVIDENCE_PATH
def validate_evidence_path():
    expected_parent = CSM_EVIDENCE_PATH.parent
    assert EVIDENCE_PATH.parent == expected_parent
    assert EVIDENCE_PATH.name == "v2-benchmark-csm-controlled-evidence.json"
    assert expected_parent.is_dir() and not EVIDENCE_PATH.is_symlink()

def save_checkpoint(state):
    validate_evidence_path()
    payload = stable_json(state)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".v2-csm-", dir=str(EVIDENCE_PATH.parent), delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(EVIDENCE_PATH))
        assert EVIDENCE_PATH.read_text(encoding="utf-8") == payload
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

lock = EVIDENCE_PATH.with_suffix(".lock")
validate_evidence_path()
descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
try:
    if EVIDENCE_PATH.exists():
        STATE = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        assert STATE["experiment_id"] == EXPERIMENT_ID and STATE["manifest"] == MANIFEST and STATE["plan"] == PLAN
    else:
        STATE = {"experiment_id": EXPERIMENT_ID, "manifest": MANIFEST, "plan": PLAN, "trials": {}, "created_at_utc": utc_now()}
        save_checkpoint(STATE)
finally:
    os.close(descriptor)
    lock.unlink()
V2_BENCHMARK_READY = True
print(
    "CSM-only checkpoint ready:",
    len(STATE["trials"]),
    "recorded of",
    len(PLAN),
    "planned trials.",
)
