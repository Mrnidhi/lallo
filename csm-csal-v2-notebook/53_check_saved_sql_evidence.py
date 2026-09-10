# Databricks notebook cell
# Check whether the saved agent responses contain usable SQL evidence.

from collections import Counter
from html import escape
import json
import re
import statistics


if "CSM_SAVED_STATE" not in globals():
    raise RuntimeError("Run the completed CSM scoring cell first.")


def walk_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, str):
        yield value
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                return
            yield from walk_strings(decoded)


def looks_like_sql(text):
    compact = " ".join(text.split())
    return bool(
        re.search(r"\b(?:SELECT|WITH)\b", compact, re.IGNORECASE)
        and re.search(r"\bFROM\b", compact, re.IGNORECASE)
    )


def sql_metrics(text):
    compact = " ".join(text.split())
    return {
        "characters": len(text),
        "lines": max(1, len(text.splitlines())),
        "joins": len(re.findall(r"\bJOIN\b", compact, re.IGNORECASE)),
        "subqueries": len(re.findall(r"\(\s*SELECT\b", text, re.IGNORECASE)),
        "starts_with_select_or_with": bool(
            re.match(r"^\s*(?:SELECT|WITH)\b", text, re.IGNORECASE)
        ),
    }


records = []
for item in CSM_SAVED_STATE["plan"]:
    trial = CSM_SAVED_STATE["trials"][item["trial_id"]]
    response = trial.get("response", {})
    sql_candidates = []
    seen = set()
    for text_value in walk_strings(response):
        if looks_like_sql(text_value):
            digest = fingerprint(text_value)
            if digest not in seen:
                seen.add(digest)
                sql_candidates.append(text_value)

    assigned_source = BASELINE if item["arm"] == "A" else BOOKING_VIEW
    records.append(
        {
            "question": item["question"],
            "arm": item["arm"],
            "repetition": item["repetition"],
            "candidate_sql_strings": len(sql_candidates),
            "assigned_source_named": any(
                assigned_source.lower() in candidate.lower()
                for candidate in sql_candidates
            ),
            "unexpected_csal_detail_named": any(
                SOURCES["detail"].lower() in candidate.lower()
                for candidate in sql_candidates
            ),
            "metrics": [sql_metrics(candidate) for candidate in sql_candidates],
        }
    )

summary = []
for arm in CSM_EXPECTED_ARMS:
    arm_records = [record for record in records if record["arm"] == arm]
    metrics = [
        metric
        for record in arm_records
        for metric in record["metrics"]
    ]
    summary.append(
        {
            "arm": arm,
            "trials": len(arm_records),
            "trials_with_sql_candidate": sum(
                record["candidate_sql_strings"] > 0 for record in arm_records
            ),
            "trials_naming_assigned_source": sum(
                record["assigned_source_named"] for record in arm_records
            ),
            "trials_naming_unexpected_csal_detail": sum(
                record["unexpected_csal_detail_named"] for record in arm_records
            ),
            "candidate_sql_strings": sum(
                record["candidate_sql_strings"] for record in arm_records
            ),
            "median_characters": (
                statistics.median(metric["characters"] for metric in metrics)
                if metrics
                else None
            ),
            "median_lines": (
                statistics.median(metric["lines"] for metric in metrics)
                if metrics
                else None
            ),
            "median_joins": (
                statistics.median(metric["joins"] for metric in metrics)
                if metrics
                else None
            ),
            "median_subqueries": (
                statistics.median(metric["subqueries"] for metric in metrics)
                if metrics
                else None
            ),
        }
    )

rows_html = "".join(
    "<tr>"
    f"<td>{escape(item['arm'])}</td>"
    f"<td>{item['trials_with_sql_candidate']}/{item['trials']}</td>"
    f"<td>{item['trials_naming_assigned_source']}/{item['trials']}</td>"
    f"<td>{item['trials_naming_unexpected_csal_detail']}/{item['trials']}</td>"
    f"<td>{escape(str(item['median_characters']))}</td>"
    f"<td>{escape(str(item['median_lines']))}</td>"
    f"<td>{escape(str(item['median_joins']))}</td>"
    f"<td>{escape(str(item['median_subqueries']))}</td>"
    "</tr>"
    for item in summary
)

displayHTML(
    f"""
    <div style="font-family:Arial,sans-serif;max-width:1100px;color:#172033">
      <h2 style="margin:0 0 8px">Saved SQL evidence check</h2>
      <p style="margin:0 0 16px;color:#526176">
        SQL text is not displayed. A candidate is counted only when a saved response string contains
        both SELECT or WITH and FROM. Candidate text is not automatically proof of executed SQL.
      </p>
      <table style="border-collapse:collapse;width:100%;font-size:14px">
        <thead><tr style="background:#e9eef7">
          <th style="text-align:left;padding:8px">Path</th>
          <th style="text-align:left;padding:8px">Trials with candidate</th>
          <th style="text-align:left;padding:8px">Assigned source named</th>
          <th style="text-align:left;padding:8px">Unexpected detail source named</th>
          <th style="text-align:left;padding:8px">Median characters</th>
          <th style="text-align:left;padding:8px">Median lines</th>
          <th style="text-align:left;padding:8px">Median joins</th>
          <th style="text-align:left;padding:8px">Median subqueries</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
)

print("CSM_SQL_EVIDENCE_SUMMARY=" + json.dumps(summary, sort_keys=True))
