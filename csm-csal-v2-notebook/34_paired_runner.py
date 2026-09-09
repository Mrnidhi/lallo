# Notebook cell 9 (file 34) | Controlled, restart-safe submissions
# Defines the runner. It does not submit questions until called from notebook cell 12.


@contextmanager
def evidence_lock():
    validate_evidence_path()
    lock_path = EVIDENCE_PATH.with_suffix(".lock")
    # A second process fails here. A leftover lock needs a human check, not auto-deletion.
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
    assert ENDPOINTS == MANIFEST["endpoints"], "Endpoint names changed after approval."
    assert WAREHOUSE_ID == MANIFEST["warehouse"]
    return {"identities": {arm: endpoint_identity(arm) for arm in ENDPOINTS},
            "schemas": {arm: fingerprint(schema) for arm, schema in ENDPOINT_SCHEMAS.items()},
            "request_contract": dict(REQUEST_CONTRACT), "timeout_seconds": HTTP_TIMEOUT_SECONDS,
            "mode": "nonstreaming_fresh_request"}


def run_next_pairs(max_trials=2):
    global STATE
    assert ENABLE_AGENT_RUNS is True and ENABLE_EVIDENCE_SAVE is True and V2_BENCHMARK_READY
    assert globals().get("V2_SCORING_SELF_TESTS_PASSED") is True, "Run the scoring self-tests first."
    assert isinstance(max_trials, int) and not isinstance(max_trials, bool) and 2 <= max_trials <= 72 and max_trials % 2 == 0
    require_preparation("questions", review_payload())
    assert REVIEW.get("draft_sha256") == MANIFEST["review"]["draft_sha256"] == fingerprint(review_payload()), "Ground-truth approval no longer matches the prepared questions."
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
        not_sent = [row for row in STATE["trials"].values() if row["state"] == "NOT_SENT"]
        assert not not_sent, "A local pre-inference failure needs review. Its request was not sent; do not silently skip or reset the trial."
        pending_checks = [row for row in STATE["trials"].values() if row["state"] == "RECEIVED" and row.get("source_check") not in {"STABLE", "INCONCLUSIVE"}]
        assert not pending_checks, "A saved response lacks its post-run controls. Do not continue until that evidence is reviewed."
        if any(row.get("source_check") == "INCONCLUSIVE" for row in STATE["trials"].values()):
            raise RuntimeError("This experiment has source-drift evidence. Stop and review before continuing.")
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
                       prompt_sha256=fingerprint(MANIFEST["prompts"][item["question"]]), request_body_sha256=prepared["body_sha256"],
                       submission_note="Saved before network submission; a crash now is uncertain, not retryable.")
            STATE["trials"][key] = row
            save_checkpoint(STATE)
            try:
                result = invoke_once(item["arm"], MANIFEST["prompts"][item["question"]], prepared=prepared)
                row.update(result, state="RECEIVED", completed_at_utc=utc_now())
            except InvocationNotSubmittedError as error:
                row.update(state="NOT_SENT", completed_at_utc=utc_now(), error_type="InvocationNotSubmittedError",
                           error_stage="authentication_or_request_preparation", source_check="NOT_RUN")
                save_checkpoint(STATE)
                raise RuntimeError("Local request preparation failed before inference. No question was sent. Review the saved NOT_SENT trial before continuing.") from None
            except HTTPError as error:
                # An HTTP error is not proof that no downstream work occurred.
                row.update(state="UNKNOWN", http_status=error.code, request_id=error.headers.get("x-databricks-request-id") if error.headers else None, completed_at_utc=utc_now(), error_type="HTTPError")
                save_checkpoint(STATE)
                raise RuntimeError("HTTP response requires review. Trial preserved without retry.") from None
            except Exception as error:
                row.update(state="UNKNOWN", completed_at_utc=utc_now(), error_type=type(error).__name__)
                save_checkpoint(STATE)
                raise RuntimeError("Request completion is uncertain. Evidence retained; no retry was made.") from None
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
            assert row["source_check"] == "STABLE", "Source state changed or could not be verified. Pair is inconclusive."
    print("New submissions:", submitted, "Recorded trials:", len(STATE["trials"]), "of 72")


def reconcile_saved_trial(key, saved_response, request_id, evidence_note, reviewer):
    # Use only the original platform record. This function never asks the agent again.
    assert reviewer.strip() and evidence_note.strip() and request_id.strip()
    assert isinstance(saved_response, dict)
    with evidence_lock():
        state = load_checkpoint()
        row = state["trials"][key]
        assert row["state"] in {"UNKNOWN", "SUBMITTED"}
        row.update(state="RECEIVED", response=saved_response, response_fingerprint=fingerprint(saved_response), request_id=request_id,
                   reconciliation={"reviewer": reviewer, "evidence": evidence_note, "at_utc": utc_now()},
                   source_check="INCONCLUSIVE", client_end_to_end_seconds=None)
        # Current markers cannot prove the source versions at a past uncertain request.
        save_checkpoint(state)
    print("Original response recovered. Timing/source comparability remains unverified; no automatic resubmission.")


print("Runner ready as a function. No agent requests were submitted by this cell.")
