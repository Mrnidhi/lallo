# Cell 8 | Check both agent connections
# This reads endpoint details and prepares the client. No question is sent here.

AGENT_CLIENT = None
AGENT_CLIENT_SETTINGS = None
assert globals().get("WorkspaceClient") is not None, "Run cell 1 first."
CLIENT_PACKAGES = {name: package_version(name) for name in ("openai", "databricks-sdk", "httpx")}
print("Client packages:", CLIENT_PACKAGES)
assert int(CLIENT_PACKAGES["openai"].split(".")[0]) < 3, "This compatibility path expects OpenAI below version 3. No question was sent."
CLIENT = WorkspaceClient()


def as_dict(value):
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, str):
        return json.loads(value)
    assert isinstance(value, dict), "Connection metadata has an unexpected format."
    return value


def endpoint_identity(arm):
    info = as_dict(CLIENT.serving_endpoints.get(name=ENDPOINTS[arm]))
    assert info.get("state", {}).get("ready") == "READY", arm + ": endpoint is not Ready."
    assert not info.get("pending_config"), arm + ": endpoint has a pending configuration."
    config = info.get("config", {})
    entities = config.get("served_entities", config.get("served_models", []))
    fields = ("name", "entity_name", "entity_version", "model_name", "model_version", "workload_size", "scale_to_zero_enabled")
    return {"name": info.get("name"), "id": info.get("id"), "config_version": config.get("config_version"),
            "entities": [{key: item.get(key) for key in fields} for item in entities],
            "traffic_config": config.get("traffic_config")}


def validate_request_settings():
    assert isinstance(ENDPOINTS, dict) and set(ENDPOINTS) == {"A", "B"}, "Exactly endpoints A and B are required."
    assert isinstance(REQUEST_CONTRACT, dict) and REQUEST_CONTRACT == {"A": "input", "B": "input"}, "Both agents use the input request format."
    assert isinstance(HTTP_TIMEOUT_SECONDS, (int, float)) and not isinstance(HTTP_TIMEOUT_SECONDS, bool), "HTTP timeout must be a number."
    assert math.isfinite(HTTP_TIMEOUT_SECONDS) and HTTP_TIMEOUT_SECONDS > 0, "HTTP timeout must be finite and positive."


def request_client_settings():
    validate_request_settings()
    assert CLIENT.config.host.rstrip("/") + "/serving-endpoints" == AGENT_BASE_URL, "Workspace host changed. Stop this run."
    assert AGENT_CLIENT.timeout == HTTP_TIMEOUT_SECONDS, "Client timeout differs from the notebook setting."
    # Inspect the private transport only to verify redirects are disabled; do not change its configuration.
    redirects = getattr(getattr(AGENT_CLIENT, "_client", None), "follow_redirects", None)
    assert redirects is False, "Cannot verify that client redirects are disabled. No question was sent."
    return {"base_url": str(AGENT_CLIENT.base_url).rstrip("/"), "timeout_seconds": AGENT_CLIENT.timeout,
            "max_retries": AGENT_CLIENT.max_retries, "follow_redirects": redirects,
            "packages": {name: package_version(name) for name in CLIENT_PACKAGES}}


def prepare_invocation(arm, prompt):
    assert V2_BENCHMARK_READY, "Run cell 7 before preparing an agent question."
    assert request_client_settings() == AGENT_CLIENT_SETTINGS, "Agent client settings changed. Stop this run."
    assert arm in {"A", "B"} and isinstance(prompt, str) and prompt.strip(), "Choose an assigned agent and a nonempty question."
    endpoint = ENDPOINTS[arm]
    assert endpoint == MANIFEST["endpoints"][arm], "Endpoint differs from the saved experiment."
    assert endpoint in {"mas-3beadca0-endpoint", "mas-6b7af80b-endpoint"}, "Only the two personal endpoints are allowed."
    return {"model": endpoint, "input": [{"role": "user", "content": prompt}], "stream": False}


def invoke_once(arm, prompt, prepared=None):
    payload = prepare_invocation(arm, prompt)
    assert prepared is None or prepared == payload, "Prepared request differs from this question."
    # Return the original HTTP response so the runner can save it before checking answers.
    return AGENT_CLIENT.responses.with_raw_response.create(**payload)


validate_request_settings()
assert ENDPOINTS == MANIFEST["endpoints"] == {"A": "mas-3beadca0-endpoint", "B": "mas-6b7af80b-endpoint"}, "Only the saved personal agent pair is allowed."
host = CLIENT.config.host.rstrip("/")
address = urlsplit(host)
assert (address.scheme == "https" and address.hostname and not address.username and not address.password
        and not address.path and not address.query and not address.fragment), "The workspace URL is not valid."
AGENT_BASE_URL = host + "/serving-endpoints"
assert callable(getattr(CLIENT.serving_endpoints, "get_open_ai_client", None)), (
    "The installed workspace SDK does not provide the existing-client helper. Share the versions above before changing packages."
)
# This deprecated helper preserves runtime compatibility for the isolated POC, not a new production integration.
AGENT_CLIENT = CLIENT.serving_endpoints.get_open_ai_client(timeout=HTTP_TIMEOUT_SECONDS, max_retries=0)
assert callable(getattr(getattr(getattr(AGENT_CLIENT, "responses", None), "with_raw_response", None), "create", None)), "The installed client does not support Responses."
AGENT_CLIENT_SETTINGS = request_client_settings()
assert AGENT_CLIENT_SETTINGS["base_url"] == AGENT_BASE_URL and AGENT_CLIENT_SETTINGS["max_retries"] == 0
assert AGENT_CLIENT_SETTINGS["timeout_seconds"] == HTTP_TIMEOUT_SECONDS
ENDPOINT_IDENTITIES = {arm: endpoint_identity(arm) for arm in ENDPOINTS}
print("Both connections are ready. Automatic retries are disabled. No question was sent.")
print("Next: run cells 9, 10 and 11. Cell 12 sends the first A/B pair.")
