# Databricks notebook cell
# Read the saved benchmark answers. This cell never contacts an agent.

state = csm_load_checkpoint()
received = []

for item in PLAN:
    trial = state["trials"].get(item["trial_id"])
    if not trial or trial.get("state") != "RECEIVED":
        continue

    response = trial.get("response", {})
    assert trial.get("response_fingerprint") == fingerprint(response), "A saved response changed."
    messages = [
        output
        for output in response.get("output", [])
        if isinstance(output, dict) and output.get("type") == "message"
    ]
    assert messages, f"No saved answer message for {item['trial_id']}."

    content = messages[-1].get("content", [])
    answer = "\n".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()
    assert answer, f"The saved answer is empty for {item['trial_id']}."

    print("\n" + "=" * 72)
    print(item["trial_id"], "|", round(trial.get("client_end_to_end_seconds", 0), 2), "seconds")
    print(answer)
    received.append(item["trial_id"])

print("\nSaved answers shown:", len(received))
