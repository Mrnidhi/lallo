# Cell 16 | Run the CSM-only controlled experiment
# Metadata-only scoped drift checks; no production writes and no duplicate submissions.
# The notebook import cell already loads time and contextmanager.

def response_problem(response):
    if response.get("status") in {"incomplete", "failed", "cancelled", "queued", "in_progress"}:
        return "Agent response status: " + response["status"]
    if response.get("error") or response.get("incomplete_details"):
        return "Agent returned an error or incomplete-response details."
    for item in response.get("output") or []:
        if isinstance(item, dict) and item.get("type") in {"task_continue_request", "error"}:
            return "Agent returned a continuation request or error item."
    return None

def current_csm_marker():
    tables = {}
    for name in sorted(CSM_DEPENDENCIES):
        detail = spark.sql("DESCRIBE DETAIL " + name).select("id", "format").first()
        assert detail["format"].lower() == "delta", "CSM source is not Delta: " + name
        history = spark.sql("DESCRIBE HISTORY " + name).select("version").orderBy(F.desc("version")).first()
        tables[name] = {
            "id": detail["id"],
            "version": int(history["version"]),
            "schema_sha256": fingerprint(spark.table(name).schema.jsonValue()),
            "format": detail["format"].lower(),
        }
    definition = spark.sql("SHOW CREATE TABLE " + BOOKING_VIEW).first()[0]
    return {"tables": tables, "booking_view_sha256": fingerprint(definition)}

def csm_load_checkpoint():
    validate_evidence_path()
    state = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert state["experiment_id"] == EXPERIMENT_ID
    assert state["manifest"] == MANIFEST
    assert state["plan"] == PLAN
    return state

def csm_evidence_lock():
    validate_evidence_path()
    path = EVIDENCE_PATH.with_suffix(".lock")
    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(descriptor)
        path.unlink()

csm_evidence_lock = contextmanager(csm_evidence_lock)

def run_next_csm_pairs(max_trials=2):
    global STATE
    assert V2_BENCHMARK_READY
    assert globals().get("V2_SCORING_SELF_TESTS_PASSED") is True
    assert isinstance(max_trials, int) and not isinstance(max_trials, bool)
    assert 2 <= max_trials <= len(PLAN) and max_trials % 2 == 0
    assert MANIFEST["reference_sha256"] == fingerprint(csm_reference_payload())
    with csm_evidence_lock():
        STATE = csm_load_checkpoint()
        transport = current_transport()
        assert STATE.get("transport", transport) == transport, (
            "Endpoint or request settings changed."
        )
        STATE["transport"] = transport
        save_checkpoint(STATE)
        assert current_csm_marker() == MANIFEST["sources"]
        saved_trials = STATE["trials"].values()
        assert not any(
            row.get("state") in {"SUBMITTED", "UNKNOWN"}
            for row in saved_trials
        ), "A prior request has uncertain completion."
        assert not any(
            row.get("source_check") == "INCONCLUSIVE"
            for row in STATE["trials"].values()
        ), "A prior source check is inconclusive."
        assert not any(
            row.get("response_problem")
            for row in STATE["trials"].values()
        ), "A prior response is incomplete."
        assert not any(
            row.get("state") == "RECEIVED"
            and row.get("source_check") != "STABLE"
            for row in STATE["trials"].values()
        ), "A prior response is missing a stable source check."
        selected = []
        for position in range(0, len(PLAN), 2):
            pair = PLAN[position:position + 2]
            missing = [item for item in pair if item["trial_id"] not in STATE["trials"]]
            if missing and len(selected) + len(missing) <= max_trials:
                selected.extend(missing)
        for item in selected:
            key = item["trial_id"]
            before = current_csm_marker()
            assert before == MANIFEST["sources"]
            prepared = prepare_invocation(item["arm"], MANIFEST["prompts"][item["question"]])
            STATE["trials"][key] = {
                "trial_id": key,
                "question": item["question"],
                "arm": item["arm"],
                "repetition": item["repetition"],
                "state": "SUBMITTED",
                "attempt": 1,
                "started_at_utc": utc_now(),
                "source_before": before,
                "transport_before": transport,
                "prompt_sha256": fingerprint(
                    MANIFEST["prompts"][item["question"]]
                ),
                "request_payload_sha256": fingerprint(prepared),
            }
            save_checkpoint(STATE)
            started = time.perf_counter()
            try:
                reply = invoke_once(item["arm"], MANIFEST["prompts"][item["question"]], prepared=prepared)
                payload = reply.http_response.json()
                assert isinstance(payload, dict), "Agent response is not a JSON object."
                STATE["trials"][key].update(
                    {
                        "http_status": reply.status_code,
                        "request_id": reply.headers.get("x-databricks-request-id")
                        or reply.headers.get("x-request-id"),
                        "state": "RECEIVED",
                        "response": payload,
                        "response_fingerprint": fingerprint(payload),
                        "response_status": payload.get("status"),
                        "response_problem": response_problem(payload),
                        "completed_at_utc": utc_now(),
                        "client_end_to_end_seconds": time.perf_counter() - started,
                    }
                )
            except Exception as exc:
                cause = exc.__cause__ or exc.__context__
                error_response = getattr(exc, "response", None)
                error_headers = getattr(error_response, "headers", {})
                STATE["trials"][key].update(
                    {
                        "state": "UNKNOWN",
                        "error_type": type(exc).__name__,
                        "error_cause_type": type(cause).__name__ if cause else None,
                        "http_status": getattr(exc, "status_code", None),
                        "request_id": error_headers.get("x-databricks-request-id")
                        or getattr(exc, "request_id", None),
                        "completed_at_utc": utc_now(),
                        "failure_elapsed_seconds": time.perf_counter() - started,
                    }
                )
                save_checkpoint(STATE)
                raise RuntimeError("Request completion is uncertain; saved UNKNOWN and will not retry.") from None
            save_checkpoint(STATE)
            after = current_csm_marker()
            transport_after = current_transport()
            STATE["trials"][key]["source_after"] = after
            STATE["trials"][key]["transport_after"] = transport_after
            stable_source = before == after == MANIFEST["sources"]
            stable_transport = transport_after == transport
            STATE["trials"][key]["source_check"] = (
                "STABLE"
                if stable_source and stable_transport
                else "INCONCLUSIVE"
            )
            save_checkpoint(STATE)
            if STATE["trials"][key]["source_check"] != "STABLE" or STATE["trials"][key].get("response_problem"):
                raise RuntimeError("Saved response is incomplete or CSM state is inconclusive; no retry was made.")
    print(
        "CSM submissions this run:",
        len(selected),
        "recorded:",
        len(STATE["trials"]),
        "of",
        len(PLAN),
    )

def csm_status():
    state = csm_load_checkpoint()
    recorded = len(state["trials"])
    reviewed = sum(bool(row.get("reviews")) for row in state["trials"].values())
    next_pair = None
    for position in range(0, len(PLAN), 2):
        pair = PLAN[position:position + 2]
        if any(item["trial_id"] not in state["trials"] for item in pair):
            next_pair = [(item["question"], item["arm"], item["repetition"]) for item in pair]
            break
    result = {"recorded": recorded, "reviewed": reviewed, "planned": len(PLAN), "next_pair": next_pair}
    print(result)
    return result
