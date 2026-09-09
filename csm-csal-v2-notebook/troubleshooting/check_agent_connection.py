# Paste into a temporary Python cell at the bottom of the existing notebook.
# Run only this cell. Do not replace or rerun cell 12, and do not use Run all.
# Read connection metadata only. No question is sent and no saved results are changed.
# Uses the imports and client already loaded by notebook cells 1 and 8.


def check_connection_only():
    endpoint = ENDPOINTS["A"]
    assert endpoint == MANIFEST["endpoints"]["A"] == "mas-3beadca0-endpoint"

    host = CLIENT.config.host.rstrip("/")
    address = urlsplit(host)
    assert (
        address.scheme == "https" and address.hostname
        and not address.username and not address.password
        and not address.path and not address.query and not address.fragment
    )

    for method in ("SDK", "HTTP"):
        started = time.perf_counter()
        stage = "metadata"

        try:
            if method == "SDK":
                CLIENT.serving_endpoints.get(name=endpoint)
            else:
                stage = "authentication"
                headers = dict(CLIENT.config.authenticate())
                request = Request(
                    host + "/api/2.0/serving-endpoints/" + endpoint,
                    headers=headers,
                    method="GET",
                )

                stage = "connection"
                with build_opener(NoRedirects()).open(request, timeout=10) as response:
                    stage = "read"
                    response.read()

            print(method, "OK",
                  round(time.perf_counter() - started, 3), "seconds")

        except Exception as error:
            print(method, "FAILED",
                  "stage:", stage,
                  "error:", type(error).__name__,
                  "HTTP:", getattr(error, "code", None),
                  "seconds:", round(time.perf_counter() - started, 3))


check_connection_only()
