# Notebook cell 8 (file 33) | Check both agent connections
# This reads connection details only. The first question is sent from cell 12.

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


def schema_unavailable_without_served_entity(error):
    # This exact response means the schema is unavailable. Other errors still stop.
    sdk_not_found = any(
        cls.__name__ == "NotFound" and (
            cls.__module__ == "databricks.sdk.errors"
            or cls.__module__.startswith("databricks.sdk.errors.")
        )
        for cls in type(error).__mro__
    )
    messages = [getattr(error, "message", None), str(error)]
    if error.args:
        messages.append(error.args[0])
    expected_message = "No entity is being served by the endpoint."
    return sdk_not_found and any(
        isinstance(message, str) and message.strip() == expected_message
        for message in messages
    )


ENDPOINT_IDENTITIES = {arm: endpoint_identity(arm) for arm in ENDPOINTS}
ENDPOINT_SCHEMAS = {}
ENDPOINT_SCHEMA_STATUS = {}
schema_reader = getattr(CLIENT.serving_endpoints, "get_open_api", None)
if callable(schema_reader):
    for arm in ENDPOINTS:
        try:
            ENDPOINT_SCHEMAS[arm] = as_dict(schema_reader(name=ENDPOINTS[arm]))
        except Exception as error:
            if not schema_unavailable_without_served_entity(error):
                raise
            ENDPOINT_SCHEMA_STATUS[arm] = {
                "status": "UNAVAILABLE_NO_SERVED_ENTITY",
                "review_required": True,
                "detail": "The schema API reported no served entity; the request format is not verified.",
            }
            REQUEST_SCHEMA_REVIEWED[arm] = False
            REQUEST_CONTRACT[arm] = None
            ENABLE_AGENT_RUNS = False
            print(arm, "Schema unavailable: the schema API reported no served entity.")
            print("Open this endpoint's existing Query/Get code example to check its request format. No question was sent.")
            continue
        schema_hash = fingerprint(ENDPOINT_SCHEMAS[arm])
        ENDPOINT_SCHEMA_STATUS[arm] = {"status": "AVAILABLE", "schema_sha256": schema_hash}
        print(arm, "OpenAPI available; schema fingerprint:", schema_hash)
else:
    ENDPOINT_SCHEMA_STATUS = {arm: {"status": "SDK_METHOD_UNAVAILABLE", "review_required": True} for arm in ENDPOINTS}
    for arm in ENDPOINTS:
        REQUEST_SCHEMA_REVIEWED[arm] = False
        REQUEST_CONTRACT[arm] = None
    ENABLE_AGENT_RUNS = False
    print("This installed SDK does not expose get_open_api. Inspect the endpoint's existing query example in the UI.")
    print("Check each endpoint separately before setting its request format.")


def show_request_schema(arm):
    assert arm in ENDPOINT_SCHEMAS, "No schema is available here. Check this endpoint's Query/Get code example in Databricks."
    print(stable_json(ENDPOINT_SCHEMAS[arm]))


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        raise RuntimeError("Unexpected redirect. No authenticated request was sent to another destination.")


class InvocationNotSubmittedError(RuntimeError):
    """Local authentication/request preparation failed before the inference call."""


def validate_request_settings():
    expected_arms = {"A", "B"}
    assert isinstance(ENDPOINTS, dict) and set(ENDPOINTS) == expected_arms, "Exactly endpoints A and B are required."
    assert isinstance(REQUEST_SCHEMA_REVIEWED, dict) and set(REQUEST_SCHEMA_REVIEWED) == expected_arms, "Request-format checks must contain exactly A and B."
    assert all(value is True for value in REQUEST_SCHEMA_REVIEWED.values()), "The request format for A and B must both be checked after cell 8."
    assert isinstance(REQUEST_CONTRACT, dict) and set(REQUEST_CONTRACT) == expected_arms, "Request contracts must contain exactly A and B."
    assert all(isinstance(value, str) and value in {"input", "messages"} for value in REQUEST_CONTRACT.values()), "Confirm both request contracts first."
    assert isinstance(HTTP_TIMEOUT_SECONDS, (int, float)) and not isinstance(HTTP_TIMEOUT_SECONDS, bool), "HTTP timeout must be a number."
    assert math.isfinite(HTTP_TIMEOUT_SECONDS) and HTTP_TIMEOUT_SECONDS > 0, "HTTP timeout must be finite and positive."


def prepare_invocation(arm, prompt):
    # Prepare the exact request before reserving a trial. Nothing is sent here.
    validate_request_settings()
    assert ENABLE_AGENT_RUNS is True and V2_BENCHMARK_READY
    assert arm in {"A", "B"} and isinstance(prompt, str) and prompt.strip(), "An assigned arm and nonempty prompt are required."
    field = REQUEST_CONTRACT[arm]
    assert callable(getattr(CLIENT.config, "authenticate", None)), "Runtime SDK authentication interface is unavailable. Stop."
    host = CLIENT.config.host.rstrip("/")
    parsed = urlsplit(host)
    assert parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment
    endpoint = ENDPOINTS[arm]
    assert endpoint == MANIFEST["endpoints"][arm], "Endpoint differs from the frozen experiment."
    assert endpoint in {"mas-3beadca0-endpoint", "mas-6b7af80b-endpoint"}
    # Use a fresh message, without a previous conversation's context.
    payload = {field: [{"role": "user", "content": prompt}]}
    body = stable_json(payload).encode("utf-8")
    url = host + "/serving-endpoints/" + endpoint + "/invocations"
    Request(url, data=body, method="POST")  # Constructor validation only.
    return {"arm": arm, "url": url, "body": body, "timeout_seconds": HTTP_TIMEOUT_SECONDS,
            "body_sha256": hashlib.sha256(body).hexdigest()}


def invoke_once(arm, prompt, prepared=None):
    prepared = prepare_invocation(arm, prompt) if prepared is None else prepared
    try:
        assert ENABLE_AGENT_RUNS is True and V2_BENCHMARK_READY
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
print("Next: use show_request_schema('A') and ('B') if available, otherwise each endpoint's Query/Get code example.")
print("Set REQUEST_CONTRACT and REQUEST_SCHEMA_REVIEWED for each endpoint after this cell's last run.")
print("Keep agent runs off. Continue with cells 9, 10 and 11.")
