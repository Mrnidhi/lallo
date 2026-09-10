# Cell 9 | Set up the paired runner
# Cell 12 calls this runner. Loading it does not send a question.


@contextmanager
def evidence_lock():
    validate_evidence_path()
    lock_path = EVIDENCE_PATH.with_suffix(".lock")
    # Only one runner can write at a time. Keep a leftover lock for investigation.
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink()


def load_checkpoint():
    assert fingerprint(MANIFEST) == EXPERIMENT_ID, "The in-memory frozen manifest was edited. Stop."
    loaded = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assert loaded["experiment_id"] == EXPERIMENT_ID and loaded["manifest"] == MANIFEST
    assert loaded["plan"] == PLAN
    assert set(loaded["trials"]).issubset({item["trial_id"] for item in PLAN})
    return loaded


def current_transport():
    validate_request_settings()
    assert ENDPOINTS == MANIFEST["endpoints"], "Endpoint names differ from the saved test setup."
    assert WAREHOUSE_ID == MANIFEST["warehouse"]
    return {"identities": {arm: endpoint_identity(arm) for arm in ENDPOINTS},
            "request_contract": dict(REQUEST_CONTRACT), "timeout_seconds": HTTP_TIMEOUT_SECONDS,
            "client": request_client_settings(), "mode": "nonstreaming_fresh_request"}


def response_problem(response):
    """Recognize an unfinished reply without trying to continue it automatically."""
    if response.get("status") in {"incomplete", "failed", "cancelled", "queued", "in_progress"}:
        return "Agent response status: " + response["status"]
    if response.get("error") or response.get("incomplete_details"):
        return "Agent returned an error or incomplete-response details."
    for item in response.get("output") or []:
        if isinstance(item, dict) and item.get("type") in {"task_continue_request", "error"}:
            return "Agent returned a continuation request or error item."
    return None


def run_next_pairs(max_trials=2):
    global STATE
    assert V2_BENCHMARK_READY, "Run cells 1-7 successfully first."
    assert globals().get("V2_SCORING_SELF_TESTS_PASSED") is True, "Run the scoring self-tests first."
    assert isinstance(max_trials, int) and not isinstance(max_trials, bool) and 2 <= max_trials <= len(PLAN) and max_trials % 2 == 0
    require_preparation("questions", review_payload())
    assert MANIFEST["reference_sha256"] == fingerprint(review_payload()), "Reference answers no longer match the saved questions. Keep this test unchanged and prepare the new setup separately."
    submitted = 0
    with evidence_lock():
        STATE = load_checkpoint()
        transport = current_transport()
        if "transport" not in STATE:
            STATE["transport"] = transport
            save_checkpoint(STATE)
        assert STATE["transport"] == transport, "Endpoint/request settings changed. Preserve this experiment."
        uncertain = [row for row in STATE["trials"].values() if row["state"] in {"SUBMITTED", "UNKNOWN"}]
        assert not uncertain, "A prior request has uncertain completion. Reconcile its existing evidence; do not resubmit it."
        assert not any(row.get("response_problem") for row in STATE["trials"].values()), (
            "A saved reply is unfinished or contains an error. Inspect it before continuing."
        )
        pending_checks = [row for row in STATE["trials"].values() if row["state"] == "RECEIVED" and row.get("source_check") not in {"STABLE", "INCONCLUSIVE"}]
        assert not pending_checks, "A saved response is missing its post-run source checks. Resolve that record before continuing."
        if any(row.get("source_check") == "INCONCLUSIVE" for row in STATE["trials"].values()):
            raise RuntimeError("Source or endpoint checks changed or could not be verified. Keep the evidence and investigate before continuing.")
        selected = []
        remaining_budget = max_trials
        for position in range(0, len(PLAN), 2):
            pair = PLAN[position:position + 2]
            missing = [item for item in pair if item["trial_id"] not in STATE["trials"]]
            if not missing:
                continue
            if len(missing) > remaining_budget:
                break
            selected.extend(missing)
            remaining_budget -= len(missing)
        for item in selected:
            key = item["trial_id"]
            if key in STATE["trials"]:
                continue  # Includes completed, error and rejected submissions; never retry an answer.
            before = source_markers()
            assert before == MANIFEST["sources"], "Sources changed since ground truth. No new request was sent."
            assert current_transport() == STATE["transport"], "Endpoint configuration drift."
            prepared = prepare_invocation(item["arm"], MANIFEST["prompts"][item["question"]])
            row = dict(item, state="SUBMITTED", attempt=1, started_at_utc=utc_now(), source_before=before,
                       prompt_sha256=fingerprint(MANIFEST["prompts"][item["question"]]), request_payload_sha256=fingerprint(prepared),
                       submission_note="Saved before network submission; a crash now is uncertain, not retryable.")
            STATE["trials"][key] = row
            save_checkpoint(STATE)
            started = time.perf_counter()
            stage = "agent_request"
            try:
                reply = invoke_once(item["arm"], MANIFEST["prompts"][item["question"]], prepared=prepared)
                row["http_status"] = reply.status_code
                row["request_id"] = reply.headers.get("x-databricks-request-id") or reply.headers.get("x-request-id")
                stage = "read_response"
                response = reply.http_response.json()
                assert isinstance(response, dict), "Agent response is not a JSON object."
                row.update(response=response, response_fingerprint=fingerprint(response),
                           response_id=response.get("id"), response_status=response.get("status"),
                           response_problem=response_problem(response),
                           state="RECEIVED", completed_at_utc=utc_now(),
                           client_end_to_end_seconds=time.perf_counter() - started)
            except Exception as error:
                # Keep the failure useful without logging tokens, headers or request bodies.
                cause = error.__cause__ or error.__context__
                error_response = getattr(error, "response", None)
                error_headers = getattr(error_response, "headers", {})
                row.update(state="UNKNOWN", completed_at_utc=utc_now(),
                           error_type=type(error).__name__, error_stage=stage,
                           error_cause_type=type(cause).__name__ if cause else None,
                           failure_elapsed_seconds=time.perf_counter() - started,
                           http_status=getattr(error, "status_code", row.get("http_status")),
                           request_id=error_headers.get("x-databricks-request-id")
                           or getattr(error, "request_id", None) or row.get("request_id"))
                save_checkpoint(STATE)
                detail = {name: row.get(name) for name in (
                    "question", "arm", "error_stage", "error_type", "error_cause_type",
                    "http_status", "request_id", "failure_elapsed_seconds")}
                print("Request failed:", stable_json(detail))
                raise RuntimeError("Request completion is uncertain. Details saved above; no retry was made.") from None
            # Persist the response before making any further metadata call.
            row["source_check"] = "PENDING"
            save_checkpoint(STATE)
            try:
                after = source_markers()
                transport_after = current_transport()
                row["source_after"] = after
                row["transport_after"] = transport_after
                row["source_check"] = "STABLE" if before == after == MANIFEST["sources"] and transport_after == STATE["transport"] else "INCONCLUSIVE"
            except Exception as error:
                row["source_check"] = "INCONCLUSIVE"
                row["source_check_error"] = type(error).__name__
            save_checkpoint(STATE)
            submitted += 1
            print(item["question"], item["arm"], "repeat", item["repetition"], row["state"], row["source_check"])
            print("Agent response status:", row.get("response_status") or "not supplied")
            print("Response:", stable_json(row["response"]))
            print("Response time:", round(row["client_end_to_end_seconds"], 2), "seconds")
            assert row["source_check"] == "STABLE", "Source state changed or could not be verified. Pair is inconclusive."
            assert not row.get("response_problem"), (
                "The agent has not supplied a completed answer. Its response is saved; inspect it without resending."
            )
    print("New submissions:", submitted, "Recorded trials:", len(STATE["trials"]), "of", len(PLAN))


print("Paired runner loaded. No question was sent.")
print("Next: run cells 10 and 11 to load and test the answer comparisons.")
