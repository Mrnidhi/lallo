# Databricks notebook cell
# Score the completed CSM checkpoint without asking either agent another question.

CSM_REPORT_TITLE = "CSM / CSAL controlled A/B comparison"
CSM_EXPECTED_QUESTIONS = ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
CSM_EXPECTED_ARMS = ["A", "B"]
CSM_EXPECTED_REPETITIONS = [1, 2, 3]
CSM_EXPECTED_TRIALS = 42
CSM_NO_MATCH_CUSTOMER = "CSM_POC_V2_NO_MATCH_20260901"

# Header matching is exact. Add a label only after its business meaning has been checked.
CSM_HEADER_ALLOWLIST = {
    "customer": ("customer", "Customer", "Customer Name"),
    "agreement": ("agreement", "Agreement", "Agreement Number"),
    "tcr": ("tcr", "TCR"),
    "confirmed_teu": ("confirmed_teu", "Confirmed TEU"),
    "cancelled_teu": ("cancelled_teu", "Cancelled TEU", "Canceled TEU"),
    "rejected_teu": ("rejected_teu", "Rejected TEU"),
    "pended_teu": ("pended_teu", "Pended TEU"),
    "terminated_teu": ("terminated_teu", "Terminated TEU"),
    "no_show_teu": ("no_show_teu", "No-show TEU", "No Show TEU"),
    "booked_teu": ("booked_teu", "Booked TEU", "Total Booked TEU"),
    "total_reviewed_teu": (
        "total_reviewed_teu",
        "Total Reviewed TEU",
        "Total Reviewed Commitment",
        "Total Reviewed Commitment TEU",
    ),
    "fulfillment_pct": (
        "fulfillment_pct",
        "fulfillment_percentage",
        "Fulfillment %",
        "Utilization %",
        "Confirmed Utilization %",
    ),
    "cancellation_pct": (
        "cancellation_pct",
        "cancellation_rate",
        "Cancellation %",
        "Cancellation Percentage",
    ),
    "rejection_pct": (
        "rejection_pct",
        "rejection_rate",
        "Rejection %",
        "Rejection Percentage",
    ),
    "booking_pct": (
        "booking_pct",
        "booking_rate",
        "booking_percentage",
        "Booking %",
        "Booking Utilization",
        "Booking Utilization %",
    ),
}


class CSMAnswerFormatError(ValueError):
    """The final answer cannot be converted to benchmark rows without guessing."""


def _csm_stable_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _csm_fingerprint(value):
    return hashlib.sha256(_csm_stable_json(value).encode("utf-8")).hexdigest()


def _csm_final_answer_text(trial):
    """Read only the final assistant message, never tool output or an earlier draft."""
    response = trial.get("response")
    if not isinstance(response, dict):
        raise CSMAnswerFormatError("The saved response is missing.")
    if trial.get("response_fingerprint") != _csm_fingerprint(response):
        raise RuntimeError("A saved response fingerprint does not match its content.")

    outputs = response.get("output")
    if not isinstance(outputs, list) or not outputs:
        raise CSMAnswerFormatError("The response has no output items.")
    final = outputs[-1]
    if not isinstance(final, dict) or final.get("type") != "message":
        raise CSMAnswerFormatError("The last output item is not a final message.")
    if final.get("role") not in (None, "assistant") or final.get("call_id"):
        raise CSMAnswerFormatError("The last output item is not a final assistant answer.")

    content = final.get("content")
    if not isinstance(content, list) or not content:
        raise CSMAnswerFormatError("The final answer has no content blocks.")
    texts = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "output_text":
            raise CSMAnswerFormatError("The final answer contains a non-text content block.")
        text = part.get("text")
        if not isinstance(text, str) or not text.strip():
            raise CSMAnswerFormatError("The final answer contains an empty text block.")
        texts.append(text.strip())
    return "\n".join(texts)


def _csm_table_blocks(text):
    """Return contiguous pipe-table blocks and reject half-formed table lines."""
    lines = text.splitlines()
    candidate_indexes = [
        index
        for index, line in enumerate(lines)
        if line.strip().startswith("|") or line.strip().endswith("|")
    ]
    if not candidate_indexes:
        return []

    blocks = []
    start = previous = candidate_indexes[0]
    for index in candidate_indexes[1:]:
        if index != previous + 1:
            blocks.append(lines[start : previous + 1])
            start = index
        previous = index
    blocks.append(lines[start : previous + 1])

    for block in blocks:
        if any(
            not line.strip().startswith("|")
            or not line.strip().endswith("|")
            or "\\|" in line
            for line in block
        ):
            raise CSMAnswerFormatError("A Markdown table delimiter is malformed or escaped.")
    return blocks


def _csm_parse_table(block):
    """Parse one strict Markdown table while preserving its displayed values."""
    if len(block) < 2:
        raise CSMAnswerFormatError("A Markdown table needs a header and separator row.")
    cells = [
        [value.strip() for value in line.strip()[1:-1].split("|")]
        for line in block
    ]
    headers = cells[0]
    if not headers or any(not header for header in headers):
        raise CSMAnswerFormatError("A Markdown table has an empty header.")
    if len(set(headers)) != len(headers):
        raise CSMAnswerFormatError("A Markdown table has duplicate headers.")
    if len(cells[1]) != len(headers) or not all(
        re.fullmatch(r":?-{3,}:?", value) for value in cells[1]
    ):
        raise CSMAnswerFormatError("A Markdown table has an invalid separator row.")
    if any(len(row) != len(headers) for row in cells[2:]):
        raise CSMAnswerFormatError("Markdown table rows have different widths.")
    if any(not value for row in cells[2:] for value in row):
        raise CSMAnswerFormatError("An empty table cell is ambiguous; use an explicit NULL.")
    return headers, [dict(zip(headers, row)) for row in cells[2:]]


def _csm_extract_tables(text):
    return [_csm_parse_table(block) for block in _csm_table_blocks(text)]


def _csm_header_mapping(required_columns, headers):
    """Map each required field through the checked allowlist without fuzzy matching."""
    mapping = {}
    used_headers = set()
    for canonical in required_columns:
        allowed = CSM_HEADER_ALLOWLIST.get(canonical, (canonical,))
        matches = [header for header in headers if header in allowed]
        if len(matches) != 1:
            raise CSMAnswerFormatError(
                f"Expected one recognized header for {canonical}; found {len(matches)}."
            )
        actual = matches[0]
        if actual in used_headers:
            raise CSMAnswerFormatError("One answer header maps to more than one required field.")
        mapping[canonical] = actual
        used_headers.add(actual)

    globally_known = {
        label
        for allowed in CSM_HEADER_ALLOWLIST.values()
        for label in allowed
    }
    extra_headers = [header for header in headers if header not in used_headers]
    unknown_headers = [header for header in extra_headers if header not in globally_known]
    return {
        "canonical_to_actual": mapping,
        "aliases": {
            canonical: actual
            for canonical, actual in mapping.items()
            if canonical != actual
        },
        "extra_headers": extra_headers,
        "unknown_headers": unknown_headers,
        "recognized_projection": not extra_headers,
    }


def _csm_prepare_rows(rows, mapping, numeric_columns):
    """Convert explicit numeric NULL tokens only; do not clean or infer other values."""
    actual_to_canonical = {
        actual: canonical
        for canonical, actual in mapping["canonical_to_actual"].items()
    }
    prepared = []
    for row in rows:
        converted = dict(row)
        for header, value in row.items():
            canonical = actual_to_canonical.get(header)
            if canonical in numeric_columns and value in {"NULL", "null"}:
                converted[header] = None
        prepared.append(converted)
    return prepared


CSM_NO_MATCH_PATTERNS = (
    r"\bno\s+(?:exact\s+)?(?:matching\s+)?(?:booking\s+)?(?:records?|rows?|results?|match(?:es)?|bookings?|summaries|summary|data)\b",
    r"\b(?:zero|0)\s+(?:matching\s+)?(?:records?|rows?|results?|match(?:es)?)\b",
    r"\b(?:could\s+not|couldn['’]t|did\s+not|didn['’]t|cannot|can['’]t)\s+find\b",
    r"\bnot\s+found\b",
    r"\breturned\s+(?:no|zero|0)\s+rows\b",
)
CSM_SUBSTITUTION_PATTERNS = (
    r"\b(?:showing|using|returning)\b.{0,40}\b(?:another|different|closest|similar|alternative)\s+customer\b",
    r"\breplaced\b.{0,30}\bwith\b.{0,30}\bcustomer\b",
)


def _csm_c07_no_match(text, parsed_tables):
    """Accept C07 only when the final answer clearly reports no rows and substitutes none."""
    if len(parsed_tables) > 1:
        return False, "More than one final-answer table was returned."
    if parsed_tables:
        headers, rows = parsed_tables[0]
        if rows:
            return False, "C07 returned data rows instead of an exact no-match."
        try:
            mapping = _csm_header_mapping(["customer", "agreement", "tcr"], headers)
        except CSMAnswerFormatError as exc:
            return False, str(exc)
        if not mapping["recognized_projection"]:
            return False, "The empty C07 table contains extra columns."

    lowered = " ".join(text.lower().split())
    explicit_no_match = any(re.search(pattern, lowered) for pattern in CSM_NO_MATCH_PATTERNS)
    substituted = any(re.search(pattern, lowered) for pattern in CSM_SUBSTITUTION_PATTERNS)
    if not explicit_no_match:
        return False, "C07 did not clearly say that the exact lookup returned no match."
    if substituted:
        return False, "C07 appears to substitute or show a different customer."
    return True, "The final answer clearly reports no match and returns no substitute rows."


def _csm_percent(numerator, denominator):
    return round(100.0 * numerator / denominator, 1) if denominator else None


def _csm_percentile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _csm_seconds(value):
    return (
        float(value)
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
        else None
    )


def _csm_score_trial(item, trial, manifest, score_function):
    question = item["question"]
    result = {
        "question": question,
        "arm": item["arm"],
        "repetition": item["repetition"],
        "state": None if trial is None else trial.get("state"),
        "correctness": "NOT_EVALUABLE",
        "row_status": "NOT_EVALUABLE",
        "answer_signature": None,
        "recognized_projection": None,
        "canonical_header_contract": None,
        "extra_headers": [],
        "unknown_headers": [],
        "narrative_check": "NOT_EVALUATED",
        "sql_check": "NOT_EVALUATED",
        "assigned_source_check": "NOT_EVALUATED",
        "source_state_check": None if trial is None else trial.get("source_check"),
        "latency_seconds": None if trial is None else _csm_seconds(
            trial.get("client_end_to_end_seconds")
        ),
        "reason": "",
    }
    if trial is None:
        result["reason"] = "The planned trial is missing from the checkpoint."
        return result
    if trial.get("state") != "RECEIVED" or trial.get("response_problem"):
        result["reason"] = trial.get("response_problem") or "The response is not complete."
        return result

    contract = manifest["contracts"][question]["answer"]
    expected = manifest["expected"][question]["answer"]
    try:
        text = _csm_final_answer_text(trial)
        tables = _csm_extract_tables(text)
        if question == "C07":
            no_match, no_match_reason = _csm_c07_no_match(text, tables)
            score = score_function(
                expected,
                [],
                contract["columns"],
                contract["precision"],
                {},
                ordered=True,
            )
            # The empty-list hash matches the reference, but it cannot prove that
            # the agent ran the exact customer filter. Keep that distinction visible.
            result["empty_list_comparison"] = score["status"]
            result["row_status"] = "NOT_EVALUABLE"
            result["answer_signature"] = None
            result["narrative_check"] = "CORRECT" if no_match else "INCORRECT"
            result["correctness"] = (
                "NOT_EVALUABLE"
                if score["status"] == "CORRECT" and no_match
                else "INCORRECT"
            )
            result["reason"] = (
                no_match_reason
                + " Exact-filter retrieval evidence is not available in this automatic review."
                if no_match
                else no_match_reason
            )
            return result

        if len(tables) != 1:
            raise CSMAnswerFormatError(
                f"Expected one final-answer table; found {len(tables)}."
            )
        headers, rows = tables[0]
        mapping = _csm_header_mapping(contract["columns"], headers)
        prepared_rows = _csm_prepare_rows(
            rows,
            mapping,
            set(contract["precision"]),
        )
        score = score_function(
            expected,
            prepared_rows,
            contract["columns"],
            contract["precision"],
            mapping["aliases"],
            ordered=True,
        )
        result.update(
            {
                "correctness": score["status"],
                "row_status": score["status"],
                "answer_signature": score.get("actual_hash"),
                "recognized_projection": mapping["recognized_projection"],
                "canonical_header_contract": score.get("contract_compliant"),
                "extra_headers": mapping["extra_headers"],
                "unknown_headers": mapping["unknown_headers"],
                "reason": "; ".join(score.get("reasons", [])),
            }
        )
        return result
    except CSMAnswerFormatError as exc:
        result["correctness"] = "INCORRECT"
        result["row_status"] = "NOT_EVALUABLE"
        result["reason"] = str(exc)
        return result
    except (ValueError, TypeError, OverflowError) as exc:
        result["correctness"] = "INCORRECT"
        result["reason"] = "The displayed values could not be compared under the fixed rules: " + str(exc)
        return result


def _csm_validate_checkpoint(state):
    if not isinstance(state, dict):
        raise RuntimeError("The CSM checkpoint is not a JSON object.")
    required = {"experiment_id", "manifest", "plan", "trials"}
    if not required <= set(state):
        raise RuntimeError("The CSM checkpoint is incomplete.")
    manifest = state["manifest"]
    if state["experiment_id"] != _csm_fingerprint(manifest):
        raise RuntimeError("The CSM manifest fingerprint is invalid.")
    if globals().get("MANIFEST") is not None and globals()["MANIFEST"] != manifest:
        raise RuntimeError("The in-memory MANIFEST differs from the saved CSM checkpoint.")

    plan = state["plan"]
    trials = state["trials"]
    expected_plan = {
        (question, arm, repetition)
        for question in CSM_EXPECTED_QUESTIONS
        for arm in CSM_EXPECTED_ARMS
        for repetition in CSM_EXPECTED_REPETITIONS
    }
    actual_plan = {
        (item.get("question"), item.get("arm"), item.get("repetition"))
        for item in plan
    }
    if len(plan) != CSM_EXPECTED_TRIALS or actual_plan != expected_plan:
        raise RuntimeError("The saved plan is not the expected 7 x 2 x 3 CSM experiment.")
    if len({item.get("trial_id") for item in plan}) != CSM_EXPECTED_TRIALS:
        raise RuntimeError("The saved CSM plan contains duplicate trial identifiers.")
    if set(trials) != {item["trial_id"] for item in plan}:
        raise RuntimeError("The CSM checkpoint does not contain all 42 planned trials exactly once.")

    for question in CSM_EXPECTED_QUESTIONS:
        if question not in manifest.get("expected", {}) or question not in manifest.get("contracts", {}):
            raise RuntimeError("The saved manifest is missing a CSM reference or contract.")
    incomplete = [
        item["trial_id"]
        for item in plan
        if trials[item["trial_id"]].get("state") != "RECEIVED"
        or trials[item["trial_id"]].get("response_problem")
    ]
    if incomplete:
        raise RuntimeError(
            f"The controlled report requires 42 completed responses; {len(incomplete)} remain incomplete."
        )
    for trial in trials.values():
        response = trial.get("response")
        if not isinstance(response, dict) or trial.get("response_fingerprint") != _csm_fingerprint(response):
            raise RuntimeError("A saved trial response failed its integrity check.")
    return manifest


def _csm_arm_summary(arm, trial_scores):
    rows = [score for score in trial_scores if score["arm"] == arm]
    statuses = Counter(score["correctness"] for score in rows)
    evaluated = statuses.get("CORRECT", 0) + statuses.get("INCORRECT", 0)
    latencies = [score["latency_seconds"] for score in rows if score["latency_seconds"] is not None]
    table_rows = [score for score in rows if score["question"] != "C07"]
    consistency = {}
    for question in CSM_EXPECTED_QUESTIONS:
        group = [
            score
            for score in rows
            if score["question"] == question
        ]
        signatures = [score["answer_signature"] for score in group]
        consistency[question] = (
            "STABLE"
            if len(group) == 3
            and all(signature is not None for signature in signatures)
            and len(set(signatures)) == 1
            else "UNSTABLE"
            if len(group) == 3 and all(signature is not None for signature in signatures)
            else "NOT_EVALUABLE"
        )
    return {
        "planned": len(rows),
        "received": sum(score["state"] == "RECEIVED" for score in rows),
        "status_counts": dict(statuses),
        "evaluated": evaluated,
        "correct": statuses.get("CORRECT", 0),
        "correct_pct_of_planned": _csm_percent(statuses.get("CORRECT", 0), len(rows)),
        "correct_pct_of_evaluated": _csm_percent(statuses.get("CORRECT", 0), evaluated),
        "c07_clear_no_match_narratives": sum(
            score["question"] == "C07" and score["narrative_check"] == "CORRECT"
            for score in rows
        ),
        "stable_question_groups": sum(value == "STABLE" for value in consistency.values()),
        "evaluable_consistency_groups": sum(
            value in {"STABLE", "UNSTABLE"} for value in consistency.values()
        ),
        "consistency": consistency,
        "recognized_projection": sum(
            score["recognized_projection"] is True for score in table_rows
        ),
        "canonical_header_contract": sum(
            score["canonical_header_contract"] is True for score in table_rows
        ),
        "table_trials": len(table_rows),
        "source_state_stable": sum(score["source_state_check"] == "STABLE" for score in rows),
        "timed_trials": len(latencies),
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "latency_q1_seconds": _csm_percentile(latencies, 0.25),
        "latency_q3_seconds": _csm_percentile(latencies, 0.75),
    }


def build_csm_offline_report(state, score_function):
    """Build aggregate evidence from stored responses only."""
    manifest = _csm_validate_checkpoint(state)
    trial_scores = [
        _csm_score_trial(
            item,
            state["trials"][item["trial_id"]],
            manifest,
            score_function,
        )
        for item in state["plan"]
    ]
    arms = {
        arm: _csm_arm_summary(arm, trial_scores)
        for arm in CSM_EXPECTED_ARMS
    }

    paired_latency_deltas = []
    for question in CSM_EXPECTED_QUESTIONS:
        for repetition in CSM_EXPECTED_REPETITIONS:
            pair = {
                score["arm"]: score
                for score in trial_scores
                if score["question"] == question and score["repetition"] == repetition
            }
            if set(pair) == {"A", "B"} and all(
                pair[arm]["latency_seconds"] is not None for arm in ("A", "B")
            ):
                paired_latency_deltas.append(
                    pair["B"]["latency_seconds"] - pair["A"]["latency_seconds"]
                )

    return {
        "title": CSM_REPORT_TITLE,
        "experiment_id": state["experiment_id"],
        "reference_status": manifest.get("reference_status", "NOT_RECORDED"),
        "received_trials": sum(score["state"] == "RECEIVED" for score in trial_scores),
        "planned_trials": len(trial_scores),
        "arms": arms,
        "trial_scores": trial_scores,
        "paired_latency": {
            "complete_pairs": len(paired_latency_deltas),
            "median_b_minus_a_seconds": (
                statistics.median(paired_latency_deltas)
                if paired_latency_deltas
                else None
            ),
        },
        "evidence_boundaries": {
            "narrative": "Not scored, except C07's explicit exact no-match statement.",
            "sql": "Not evaluated. Complete structured SQL traces are not guaranteed in this checkpoint.",
            "source": (
                "The recorded STABLE marker checks source state before and after a request. "
                "It does not prove which table or view the agent queried."
            ),
            "latency": "Client end-to-end response time, not SQL execution time or user-interface latency.",
            "causality": (
                "This compares the complete personal wide and curated access paths. "
                "It does not isolate table design from agent instructions, routing or managed-model behavior."
            ),
        },
    }


def _csm_format_seconds(value):
    return "unavailable" if value is None else f"{value:.2f} s"


def show_csm_offline_report(report):
    """Print a compact manager-ready comparison without exposing returned customer rows."""
    print("\n" + report["title"])
    print("=" * len(report["title"]))
    print(
        f"Completed responses: {report['received_trials']}/{report['planned_trials']} | "
        f"Reference status: {report['reference_status']}"
    )
    print("\nMetric | A: wide baseline | B: curated booking view")
    print("--- | --- | ---")
    arm_a = report["arms"]["A"]
    arm_b = report["arms"]["B"]
    print(
        "Proven correct out of all planned trials | "
        f"{arm_a['correct']}/{arm_a['planned']} ({arm_a['correct_pct_of_planned']:.1f}%) | "
        f"{arm_b['correct']}/{arm_b['planned']} ({arm_b['correct_pct_of_planned']:.1f}%)"
    )
    accuracy_a = arm_a["correct_pct_of_evaluated"]
    accuracy_b = arm_b["correct_pct_of_evaluated"]
    print(
        "Accuracy among evaluable table answers | "
        f"{arm_a['correct']}/{arm_a['evaluated']} "
        f"({'unavailable' if accuracy_a is None else f'{accuracy_a:.1f}%'}) | "
        f"{arm_b['correct']}/{arm_b['evaluated']} "
        f"({'unavailable' if accuracy_b is None else f'{accuracy_b:.1f}%'})"
    )
    print(
        "Clear C07 no-match narratives, not retrieval-proven | "
        f"{arm_a['c07_clear_no_match_narratives']}/3 | "
        f"{arm_b['c07_clear_no_match_narratives']}/3"
    )
    print(
        "Stable evaluable question groups | "
        f"{arm_a['stable_question_groups']}/{arm_a['evaluable_consistency_groups']} | "
        f"{arm_b['stable_question_groups']}/{arm_b['evaluable_consistency_groups']}"
    )
    print(
        "Median response time | "
        f"{_csm_format_seconds(arm_a['median_latency_seconds'])} | "
        f"{_csm_format_seconds(arm_b['median_latency_seconds'])}"
    )
    print(
        "Only requested recognized columns | "
        f"{arm_a['recognized_projection']}/{arm_a['table_trials']} | "
        f"{arm_b['recognized_projection']}/{arm_b['table_trials']}"
    )
    print(
        "Canonical column names | "
        f"{arm_a['canonical_header_contract']}/{arm_a['table_trials']} | "
        f"{arm_b['canonical_header_contract']}/{arm_b['table_trials']}"
    )
    print(
        "Recorded source state stayed unchanged | "
        f"{arm_a['source_state_stable']}/{arm_a['planned']} | "
        f"{arm_b['source_state_stable']}/{arm_b['planned']}"
    )

    print("\nQuestion | A correct | B correct | A consistency | B consistency")
    print("--- | --- | --- | --- | ---")
    for question in CSM_EXPECTED_QUESTIONS:
        scores_a = [
            row for row in report["trial_scores"]
            if row["question"] == question and row["arm"] == "A"
        ]
        scores_b = [
            row for row in report["trial_scores"]
            if row["question"] == question and row["arm"] == "B"
        ]
        correct_a = sum(row["correctness"] == "CORRECT" for row in scores_a)
        correct_b = sum(row["correctness"] == "CORRECT" for row in scores_b)
        print(
            f"{question} | {correct_a}/3 | {correct_b}/3 | "
            f"{arm_a['consistency'][question]} | {arm_b['consistency'][question]}"
        )

    delta = report["paired_latency"]["median_b_minus_a_seconds"]
    print(
        "\nMedian paired response-time difference, B minus A:",
        _csm_format_seconds(delta),
    )
    print("\nEvidence boundaries")
    for label, note in report["evidence_boundaries"].items():
        print(f"- {label.capitalize()}: {note}")


def _csm_reporter_self_tests():
    """Check strict extraction rules with synthetic answers only."""
    tests = 0

    def expect_error(action):
        nonlocal tests
        try:
            action()
        except CSMAnswerFormatError:
            tests += 1
            return
        raise AssertionError("A malformed synthetic answer was accepted.")

    canonical = """Here is the result.
| customer | agreement | tcr | confirmed_teu |
|---|---|---|---:|
| Example | A1 | HKG | 12.5 |
"""
    blocks = _csm_extract_tables(canonical)
    assert len(blocks) == 1 and blocks[0][1][0]["confirmed_teu"] == "12.5"
    tests += 1

    friendly = """| Customer | Agreement Number | TCR | Confirmed TEU |
|---|---|---|---|
| Example | A1 | HKG | 12.5 |
"""
    headers, rows = _csm_extract_tables(friendly)[0]
    mapping = _csm_header_mapping(
        ["customer", "agreement", "tcr", "confirmed_teu"],
        headers,
    )
    assert mapping["aliases"]["agreement"] == "Agreement Number" and len(rows) == 1
    tests += 1

    response = {
        "output": [
            {"type": "function_call_output", "output": "synthetic tool output"},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": canonical}],
            },
        ]
    }
    trial = {"response": response, "response_fingerprint": _csm_fingerprint(response)}
    assert _csm_final_answer_text(trial).startswith("Here is the result.")
    tests += 1

    expect_error(lambda: _csm_extract_tables("| customer |\n| wrong |\n| A |"))
    expect_error(
        lambda: _csm_header_mapping(
            ["customer", "agreement"],
            ["Customer", "Unverified Agreement Label"],
        )
    )
    expect_error(
        lambda: _csm_header_mapping(
            ["customer"],
            ["customer", "Customer"],
        )
    )
    broken_final = {"output": [{"type": "function_call_output", "output": "not final"}]}
    expect_error(
        lambda: _csm_final_answer_text(
            {
                "response": broken_final,
                "response_fingerprint": _csm_fingerprint(broken_final),
            }
        )
    )

    ok, _ = _csm_c07_no_match(
        f"No matching records were found for {CSM_NO_MATCH_CUSTOMER}.",
        [],
    )
    assert ok
    tests += 1
    ok, _ = _csm_c07_no_match("No exact match was found for the specified customer.", [])
    assert ok
    tests += 1
    ok, _ = _csm_c07_no_match("I couldn’t find any booking data for that customer.", [])
    assert ok
    tests += 1
    not_ok, _ = _csm_c07_no_match(
        "No match was found, so I am showing a similar customer.",
        [],
    )
    assert not not_ok
    tests += 1
    c07_table = _csm_extract_tables(
        "| customer | agreement | tcr |\n|---|---|---|\n| Other | A1 | HKG |"
    )
    not_ok, _ = _csm_c07_no_match("No exact match was found.", c07_table)
    assert not not_ok
    tests += 1
    return tests


CSM_REPORTER_SELF_TEST_COUNT = _csm_reporter_self_tests()
CSM_REPORTER_SELF_TESTS_PASSED = True
print(f"Offline reporter checks passed: {CSM_REPORTER_SELF_TEST_COUNT} synthetic cases.")

if not callable(globals().get("score_section")):
    print("Load the existing verified score_section cell, then run this cell again.")
else:
    configured_path = globals().get("CSM_EVIDENCE_PATH") or globals().get("EVIDENCE_PATH")
    evidence_path = (
        Path(configured_path)
        if configured_path is not None
        else Path(
            "/Workspace/Users/jayarsr@oocl.com/Sales AI EDA/"
            "v2-benchmark-csm-controlled-evidence.json"
        )
    )
    if evidence_path.name != "v2-benchmark-csm-controlled-evidence.json":
        raise RuntimeError("This report can read only the separate CSM controlled checkpoint.")
    if evidence_path.is_symlink() or not evidence_path.is_file():
        raise RuntimeError("The CSM controlled checkpoint is unavailable at the expected personal path.")
    with evidence_path.open("r", encoding="utf-8") as stream:
        CSM_SAVED_STATE = json.load(stream)
    CSM_FINAL_REPORT = build_csm_offline_report(CSM_SAVED_STATE, score_section)
    show_csm_offline_report(CSM_FINAL_REPORT)
