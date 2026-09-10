# Resume the saved routing benchmark without rebuilding the reference answers.
# Run imports, settings, and read-only source checks before this cell.

V2_BENCHMARK_READY = False

required_names = [
    "EVIDENCE_PATH",
    "PERSONAL_OWNER",
    "BASELINE",
    "BASELINE_VERSION",
    "BOOKING_VIEW",
    "SOURCES",
    "CSM_DEPENDENCIES",
    "SCOPE",
    "MEASURES",
    "BOOKING_MEASURES",
    "FLAGS",
    "FILTERS",
    "MISSING_CUSTOMER",
    "DAILY_OUTLOOK_TASK",
    "SALES_OVERRIDES",
    "QUESTION_IDS",
    "REPETITIONS",
    "WORDING_VERSION",
    "CODE_VERSION",
    "ENDPOINTS",
    "WAREHOUSE_ID",
    "ROUTING_CONTRACT",
    "SESSION_TIME_ZONE",
]
missing_names = [name for name in required_names if name not in globals()]
assert not missing_names, "Run imports, settings, and source checks first: " + ", ".join(missing_names)


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "asDict"):
        return value.asDict(recursive=True)
    raise TypeError("Unsupported evidence value: " + type(value).__name__)


def stable_json(value):
    return json.dumps(
        value,
        default=json_value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def fingerprint(value):
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_evidence_path():
    expected_parent = Path("/Workspace/Users/" + PERSONAL_OWNER + "/Sales AI EDA")
    assert EVIDENCE_PATH.parent == expected_parent
    assert EVIDENCE_PATH.name == "v2-benchmark-routing1-evidence.json"
    assert expected_parent.is_dir(), "The personal evidence folder is unavailable."
    assert not EVIDENCE_PATH.is_symlink(), "Unexpected evidence-file symlink."


validate_evidence_path()
assert EVIDENCE_PATH.exists(), "The routing benchmark checkpoint does not exist. Do not create a replacement here."

STATE = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
required_state_keys = {"experiment_id", "manifest", "plan", "trials"}
assert required_state_keys <= set(STATE), "The saved checkpoint is incomplete."

MANIFEST = STATE["manifest"]
EXPERIMENT_ID = STATE["experiment_id"]
PLAN = STATE["plan"]

assert fingerprint(MANIFEST) == EXPERIMENT_ID, "The saved manifest fingerprint is invalid."
assert MANIFEST["label"] == "sales_ai_v2_first12_routing_01"
assert MANIFEST["code_version"] == CODE_VERSION
assert MANIFEST["wording_version"] == WORDING_VERSION
assert MANIFEST["endpoints"] == ENDPOINTS
assert MANIFEST["warehouse"] == WAREHOUSE_ID
assert MANIFEST["baseline_version"] == BASELINE_VERSION
assert MANIFEST["repetitions"] == REPETITIONS
assert MANIFEST["routing_contract"] == ROUTING_CONTRACT

SOURCE_MARKER = MANIFEST["sources"]
PROMPTS = MANIFEST["prompts"]
GT = MANIFEST["expected"]
GT_SQL = MANIFEST["ground_truth_sql"]
GT_PARAMETERS = MANIFEST["ground_truth_parameters"]
CONTRACTS = MANIFEST["contracts"]
TRACEABILITY = MANIFEST["traceability"]
LOOKUP_FIXTURE = MANIFEST["fixtures"]["lookup"]
SALES_FIXTURES = MANIFEST["fixtures"]["sales"]
METHOD_VERSION = MANIFEST["method_version"]
DRAFT_REVIEW_SHA256 = MANIFEST["reference_sha256"]

assert list(PROMPTS) == QUESTION_IDS, "Question order differs from the saved experiment."
assert set(STATE["trials"]) <= {item["trial_id"] for item in PLAN}


def preparation_inputs():
    return {
        "owner": PERSONAL_OWNER,
        "baseline": BASELINE,
        "version": BASELINE_VERSION,
        "view": BOOKING_VIEW,
        "sources": SOURCES,
        "dependencies": CSM_DEPENDENCIES,
        "scope": SCOPE,
        "measures": MEASURES,
        "booking_measures": BOOKING_MEASURES,
        "flags": FLAGS,
        "filters": FILTERS,
        "missing_customer": MISSING_CUSTOMER,
        "outlook_task": DAILY_OUTLOOK_TASK,
        "sales_overrides": SALES_OVERRIDES,
        "questions": QUESTION_IDS,
        "repetitions": REPETITIONS,
        "wording_version": WORDING_VERSION,
        "code_version": CODE_VERSION,
        "endpoints": ENDPOINTS,
        "warehouse": WAREHOUSE_ID,
        "timezone": SESSION_TIME_ZONE,
    }


def booking_payload():
    question_ids = ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
    return {
        "expected": {key: GT.get(key) for key in question_ids},
        "sql": {key: GT_SQL.get(key) for key in question_ids},
        "parameters": {key: GT_PARAMETERS.get(key) for key in question_ids},
        "contracts": {key: CONTRACTS.get(key) for key in question_ids},
        "lookup": LOOKUP_FIXTURE,
        "source_state": SOURCE_MARKER,
    }


def ground_truth_payload():
    return {
        "expected": GT,
        "sql": GT_SQL,
        "parameters": GT_PARAMETERS,
        "contracts": CONTRACTS,
        "lookup": LOOKUP_FIXTURE,
        "sales": SALES_FIXTURES,
        "source_state": SOURCE_MARKER,
    }


def review_payload():
    return {
        "ground_truth": ground_truth_payload(),
        "prompts": PROMPTS,
        "traceability": TRACEABILITY,
        "method_version": METHOD_VERSION,
        "inputs": preparation_inputs(),
    }


def preparation_stamp(stage, payload):
    PREPARATION_STAMPS[stage] = {
        "inputs": fingerprint(preparation_inputs()),
        "content": fingerprint(payload),
    }


def require_preparation(stage, payload):
    expected = {
        "inputs": fingerprint(preparation_inputs()),
        "content": fingerprint(payload),
    }
    assert PREPARATION_STAMPS.get(stage) == expected, (
        "The saved preparation contract changed at stage: " + stage
    )


PREPARATION_STAMPS = {}
for stage, payload in (
    ("sources", SOURCE_MARKER),
    ("booking", booking_payload()),
    ("shared", ground_truth_payload()),
    ("questions", review_payload()),
):
    preparation_stamp(stage, payload)

assert fingerprint(review_payload()) == DRAFT_REVIEW_SHA256, (
    "Current settings do not reproduce the saved reference contract."
)
assert spark.conf.get("spark.sql.session.timeZone") == SESSION_TIME_ZONE


def trial_id(qid, arm, repetition):
    return fingerprint([EXPERIMENT_ID, qid, arm, repetition])


def save_checkpoint(state):
    validate_evidence_path()
    payload = stable_json(state)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".v2-evidence-",
            dir=str(EVIDENCE_PATH.parent),
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(EVIDENCE_PATH))
        assert EVIDENCE_PATH.read_text(encoding="utf-8") == payload, (
            "Evidence read-back failed."
        )
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


@contextmanager
def evidence_lock():
    validate_evidence_path()
    lock_path = EVIDENCE_PATH.with_suffix(".lock")
    descriptor = os.open(
        str(lock_path),
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink()


def load_checkpoint():
    validate_evidence_path()
    assert fingerprint(MANIFEST) == EXPERIMENT_ID
    loaded = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert loaded["experiment_id"] == EXPERIMENT_ID
    assert loaded["manifest"] == MANIFEST
    assert loaded["plan"] == PLAN
    assert set(loaded["trials"]) <= {item["trial_id"] for item in PLAN}
    return loaded


STATE = load_checkpoint()
uncertain_trials = [
    row for row in STATE["trials"].values()
    if row.get("state") in {"SUBMITTED", "UNKNOWN"}
]
assert not uncertain_trials, (
    "The checkpoint contains an uncertain request. Inspect it without resubmitting."
)

completed = sum(row.get("state") == "RECEIVED" for row in STATE["trials"].values())
reviewed = sum(bool(row.get("reviews")) for row in STATE["trials"].values())
V2_BENCHMARK_READY = True

print("Saved routing benchmark restored without source or ground-truth scans.")
print("Recorded responses:", completed, "of", len(PLAN))
print("Reviewed responses:", reviewed, "of", len(PLAN))
print("Next: load the endpoint, runner, comparison, and scorer cells.")
