# Notebook cell 8 (file 33) | Check both agent connections
# This reads connection details only. The first question is sent from cell 12.
# Both endpoints' Query/Get code examples use input messages with user text.

CLIENT = WorkspaceClient()


def as_dict(value):
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, str):
        return json.loads(value)
    assert isinstance(value, dict), "Connection metadata has an unexpected format. Inspect it before continuing."
    return value


def endpoint_identity(arm):
    info = as_dict(CLIENT.serving_endpoints.get(name=ENDPOINTS[arm]))
    state = info.get("state", {})
    assert state.get("ready") == "READY", arm + ": endpoint is not Ready."
    assert not info.get("pending_config"), arm + ": endpoint has a pending configuration."
    config = info.get("config", {})
    entities = config.get("served_entities", config.get("served_models", []))
    # Keep only configuration fields needed to detect a changed endpoint.
    safe_entities = [{key: item.get(key) for key in ["name", "entity_name", "entity_version", "model_name", "model_version", "workload_size", "scale_to_zero_enabled"]} for item in entities]
    return {"name": info.get("name"), "id": info.get("id"), "config_version": config.get("config_version"),
            "entities": safe_entities, "traffic_config": config.get("traffic_config")}


ENDPOINT_IDENTITIES = {arm: endpoint_identity(arm) for arm in ENDPOINTS}


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        raise RuntimeError("Unexpected redirect. No authenticated request was sent to another destination.")


class InvocationNotSubmittedError(RuntimeError):
    """Local authentication/request preparation failed before the inference call."""


def validate_request_settings():
    expected_arms = {"A", "B"}
    assert isinstance(ENDPOINTS, dict) and set(ENDPOINTS) == expected_arms, "Exactly endpoints A and B are required."
    assert isinstance(REQUEST_CONTRACT, dict) and set(REQUEST_CONTRACT) == expected_arms, "Request contracts must contain exactly A and B."
    assert all(isinstance(value, str) and value == "input" for value in REQUEST_CONTRACT.values()), (
        "Both endpoints use the observed input request format. Set REQUEST_CONTRACT to {'A': 'input', 'B': 'input'}."
    )
    assert isinstance(HTTP_TIMEOUT_SECONDS, (int, float)) and not isinstance(HTTP_TIMEOUT_SECONDS, bool), "HTTP timeout must be a number."
    assert math.isfinite(HTTP_TIMEOUT_SECONDS) and HTTP_TIMEOUT_SECONDS > 0, "HTTP timeout must be finite and positive."


def prepare_invocation(arm, prompt):
    # Prepare the exact request before reserving a trial. Nothing is sent here.
    validate_request_settings()
    assert V2_BENCHMARK_READY, "Run cell 7 to save or load the experiment before preparing a question."
    assert arm in {"A", "B"} and isinstance(prompt, str) and prompt.strip(), "An assigned arm and nonempty prompt are required."
    assert callable(getattr(CLIENT.config, "authenticate", None)), "Runtime SDK authentication interface is unavailable. Stop."
    host = CLIENT.config.host.rstrip("/")
    parsed = urlsplit(host)
    assert parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment
    endpoint = ENDPOINTS[arm]
    assert endpoint == MANIFEST["endpoints"][arm], "Endpoint differs from the frozen experiment."
    assert endpoint in {"mas-3beadca0-endpoint", "mas-6b7af80b-endpoint"}
    # Use a fresh message, without a previous conversation's context.
    payload = {"input": [{"role": "user", "content": prompt}]}
    body = stable_json(payload).encode("utf-8")
    url = host + "/serving-endpoints/" + endpoint + "/invocations"
    Request(url, data=body, method="POST")  # Constructor validation only.
    return {"arm": arm, "url": url, "body": body, "timeout_seconds": HTTP_TIMEOUT_SECONDS,
            "body_sha256": hashlib.sha256(body).hexdigest()}


def invoke_once(arm, prompt, prepared=None):
    prepared = prepare_invocation(arm, prompt) if prepared is None else prepared
    try:
        assert V2_BENCHMARK_READY, "Run cell 7 to save or load the experiment before sending a question."
        assert prepared == prepare_invocation(arm, prompt), "Prepared request differs from this test's endpoint or question."
        assert prepared["arm"] == arm
        headers = dict(CLIENT.config.authenticate())
        assert all(isinstance(key, str) and isinstance(value, str) and key and "\r" not in key + value and "\n" not in key + value for key, value in headers.items()), "Invalid authentication headers."
        headers["Content-Type"] = "application/json"
        request = Request(prepared["url"], data=prepared["body"], headers=headers, method="POST")
        opener = build_opener(NoRedirects())
    except Exception as error:
        # Authentication may refresh credentials, but no inference call has begun.
        raise InvocationNotSubmittedError(type(error).__name__) from None
    started = time.perf_counter()
    # Send once. A timeout can leave the server outcome unknown.
    with opener.open(request, timeout=prepared["timeout_seconds"]) as response:
        raw = response.read().decode("utf-8")
        result = json.loads(raw)
        return {"response": result, "raw_response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "response_fingerprint": fingerprint(result), "client_end_to_end_seconds": time.perf_counter() - started,
                "http_status": response.status, "request_id": response.headers.get("x-databricks-request-id"),
                "response_id": result.get("id") if isinstance(result, dict) else None}


print("Connection inspection finished. No question was sent.")
print("Both agents use a fresh input message containing only this question's user text.")
print("Next: run cells 9, 10 and 11 to load the runner and check scoring. Cell 12 sends the first A/B pair.")
