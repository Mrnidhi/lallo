"""Build the ten-cell Markdown copy guide from TEN_EVIDENCE_SQL_PACK.sql."""

from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "TEN_EVIDENCE_SQL_PACK.sql"
TARGET = HERE / "TEN_EVIDENCE_COPY_CELLS.md"

CASES = [
    ("E01", "Monthly booked TEU", "MONTHLY", "monthly_booked_teu", "booked_teu",
     "For the selected month, what is total monthly booked TEU?"),
    ("E02", "Monthly cancelled TEU", "MONTHLY", "monthly_cancelled_teu", "cancelled_teu",
     "For the selected month, what is total monthly cancelled TEU?"),
    ("E03", "Monthly rejected TEU", "MONTHLY", "monthly_rejected_teu", "rejected_teu",
     "For the selected month, what is total monthly rejected TEU?"),
    ("E04", "Monthly confirmed TEU", "MONTHLY", "monthly_confirmed_teu", "confirmed_teu",
     "For the selected month, what is total monthly confirmed TEU?"),
    ("E05", "Booked TEU", "BOOKING", "booked_teu", "booked_teu",
     "For the selected month, what is total booked TEU?"),
    ("E06", "Confirmed TEU", "BOOKING", "confirmed_teu", "confirmed_teu",
     "For the selected month, what is total confirmed TEU?"),
    ("E07", "Cancelled TEU", "BOOKING", "cancelled_teu", "cancelled_teu",
     "For the selected month, what is total cancelled TEU?"),
    ("E08", "Rejected TEU", "BOOKING", "rejected_teu", "rejected_teu",
     "For the selected month, what is total rejected TEU?"),
    ("E09", "No-show TEU", "BOOKING", "no_show_teu", "no_show_teu",
     "For the selected month, what is total no-show TEU?"),
    ("E10", "Terminated TEU", "BOOKING", "terminated_teu", "terminated_teu",
     "For the selected month, what is total terminated TEU?"),
]


text = SOURCE.read_text()
main = text.split("-- DBTITLE 1,5. Run all ten cases or one selected evidence ID\n", 1)[1]
main = main.split("\n-- COMMAND ----------", 1)[0].strip()

catalog_pattern = re.compile(
    r"metric_catalog AS \(\n  SELECT \* FROM VALUES\n.*?"
    r"  AS t\(evidence_id, evidence_scope, gold_metric, upstream_metric, production_question\)\n\),",
    re.S,
)

intro = """# CSM/CSAL ten-metric Databricks SQL audit

This guide contains ten numbered, self-contained, read-only SQL cells. It creates no table or view. It does not claim that any total is correct before execution. Each cell keeps five items separate: the physical Gold sum, a count-once calculation at the tested Gold grouping, a replay of the retained producer code, a guarded intermediate calculation, and an optional independent raw-source reference.

The intermediate table is `dev.crmi_gold.csal_teu_performance`. It is another curated Gold object, not independent raw truth. The final agent-error label stays blocked until the raw movement and shipment-status calculation, executed agent trace, identity rule, metric rule and snapshot alignment are all confirmed.

This is a diagnostic worksheet, not a self-contained raw-source proof. It discovers possible raw object names but does not invent the missing deployed producer revision or raw snapshot. Enter an independently executed raw rebuild result only after those items are verified in the approved workspace.

This worksheet creates nothing under any user. `madabra` is not the owner. Any later, separately approved V3 materialization must target only `usr.jayarsr` after the signed-in identity and schema are confirmed.

## Parameters to create in Databricks

Create these named parameters once in the SQL editor or notebook UI:

| Parameter | Type | Value to enter |
|---|---|---|
| `report_month` | String | The exact month label, for example `August 2026` |
| `gold_version` | Integer | The selected `csm_csal_summary` Delta version |
| `upstream_version` | Integer | The selected `csal_teu_performance` Delta version |
| `agent_answer_value` | String | Leave blank for the initial ten-cell diagnostic pass. Enter the numeric production-agent answer only when rerunning one case |
| `independent_raw_reference_total` | String | Leave blank until the raw-source rebuild is complete for that case |
| `identity_rule_confirmed` | Integer | `0` until the identity rule is approved, otherwise `1` |
| `metric_rule_confirmed` | Integer | `0` until additivity and status rules are approved, otherwise `1` |
| `lineage_alignment_confirmed` | Integer | `0` until both pinned versions are tied to the same producer run, otherwise `1` |
| `raw_source_validation_confirmed` | Integer | `0` until raw-source completeness checks pass, otherwise `1` |
| `agent_trace_executed_confirmed` | Integer | `0` until the executed agent SQL or tool trace is captured, otherwise `1` |
| `agent_scope_alignment_confirmed` | Integer | `0` until source, month, filters and version align, otherwise `1` |
| `agent_unsafe_aggregation_confirmed` | Integer | `0` until the trace shows that repeated values were summed, otherwise `1` |

Use only `0` or `1` for every control. A missing check stays `0`. Do not use the latest version automatically. First run the two history statements below, choose explicit versions, and capture both selected rows.

```sql
DESCRIBE HISTORY `dev`.`sales_ai_assistant_gold`.`csm_csal_summary`;
```

```sql
DESCRIBE HISTORY `dev`.`crmi_gold`.`csal_teu_performance`;
```

If the Databricks surface rejects a parameter marker after `VERSION AS OF`, replace only that marker with the already verified numeric version in the private office copy. Do not replace it with an unpinned current-table read.

Confirm that the selected month exists in both pinned snapshots before running the evidence cells:

```sql
SELECT 'GOLD' AS layer, :gold_version AS version, :report_month AS report_month, COUNT(*) AS rows
FROM `dev`.`sales_ai_assistant_gold`.`csm_csal_summary` VERSION AS OF :gold_version
WHERE month = :report_month
UNION ALL
SELECT 'UPSTREAM', :upstream_version, :report_month, COUNT(*)
FROM `dev`.`crmi_gold`.`csal_teu_performance` VERSION AS OF :upstream_version
WHERE month = :report_month;
```

## Raw-source name check

The retained screenshots and secondary notes disagree on the raw shipment schema spelling. Run this discovery query before writing or accepting any raw-source reference. It only reports visible metadata.

```sql
WITH candidates(source_role, table_catalog, table_schema, table_name) AS (
  SELECT * FROM VALUES
    ('MOVEMENT', 'datasources', 'dmsa_dm_pb_shp',  'dmsa_pb_shp_mvmt'),
    ('SHIPMENT', 'datasources', 'dmsa_dm_pb_shp',  'dmsa_pb_shp_shipment'),
    ('MOVEMENT', 'datasources', 'dimsa_dm_pb_shp', 'dimsa_pb_shp_mvmt'),
    ('SHIPMENT', 'datasources', 'dimsa_dm_pb_shp', 'dimsa_pb_shp_shipment'),
    ('TCR_MAP',  'datasources', 'csal',            'gsp_org_flattn_hierarchy'),
    ('TCR_MAP',  'datasources', 'cisp',            'org_flattn_hierarchy')
)
SELECT c.source_role, c.table_catalog, c.table_schema, c.table_name,
       CASE WHEN t.table_name IS NULL THEN 'NOT_VISIBLE' ELSE 'VISIBLE' END AS visibility
FROM candidates c
LEFT JOIN system.information_schema.tables t
  ON LOWER(t.table_catalog) = LOWER(c.table_catalog)
 AND LOWER(t.table_schema) = LOWER(c.table_schema)
 AND LOWER(t.table_name) = LOWER(c.table_name)
ORDER BY c.source_role, c.table_schema, c.table_name;
```

Visibility alone is not enough. The executed producer revision must name the same movement, shipment and TCR-map objects. Keep `raw_source_validation_confirmed = 0` if the pair is ambiguous, the code revision is unverified, the source cannot be time-aligned, or the raw calculation has unresolved join multiplication.

## Run order

1. Capture the two history rows and the two snapshot row counts.
2. For the first diagnostic pass, leave both numeric evidence inputs blank, keep all controls at `0`, and run Cells 1 through 10 without changing the pinned month or versions.
3. Stop and investigate if a cell reports blocked groups, hidden producer conflicts, an empty scope, multiple upstream run dates, integer-conversion risk, cross-month merging, unmatched allocation rows or an unsurfaced monthly group.
4. Keep the eligible subtotal visible, but never use it as a complete answer when a blocked count is nonzero.
5. Rebuild the reference from the verified movement and shipment-status sources. Record the result in `independent_raw_reference_total` only when its required joins, filters, status rules and snapshot alignment pass.
6. Ask the production main agent the matching question in a fresh chat. Retain the answer and the executed SQL, UC-function call or tool trace. Do not use a proposed SQL statement as proof that it executed.
7. Rerun one evidence cell at a time with only that case's agent answer and raw reference. Change a control to `1` only when its named evidence exists. Never reuse one case's numbers for another case.
8. Capture the SQL code, complete output and version metadata for every case. Avoid customer-level rows in the report.

## Reading the conclusion

- `technical_result` describes only the pattern visible between the pinned Gold and guarded intermediate data.
- `business_validation_status` records whether the grouping and metric meaning are approved.
- `agent_error_attribution` is the final conclusion. It remains unresolved when any required evidence is absent.
- Ten result rows are ten related metric checks from one pipeline, not ten independent experiments and not an overall production-agent accuracy score.

"""

parts = [intro]
for number, (eid, title, scope, gold_metric, upstream_metric, question) in enumerate(CASES, 1):
    row = (
        "metric_catalog AS (\n"
        "  SELECT * FROM VALUES\n"
        f"    ('{eid}', '{scope}', '{gold_metric}', '{upstream_metric}', '{question}')\n"
        "  AS t(evidence_id, evidence_scope, gold_metric, upstream_metric, production_question)\n"
        "),"
    )
    query, substitutions = catalog_pattern.subn(row, main, count=1)
    if substitutions != 1:
        raise RuntimeError(f"Could not narrow metric catalog for {eid}")
    query = query.replace(
        "WHERE UPPER(:evidence_id) = 'ALL' OR evidence_id = UPPER(:evidence_id)",
        f"WHERE evidence_id = '{eid}'",
    )
    query = query.replace("UPPER(:evidence_id)", f"'{eid}'")
    parts.append(
        f"## Cell {number}: {eid} {title}\n\n"
        f"Production-agent question to capture after the SQL run: **{question}**\n\n"
        "```sql\n"
        f"-- {eid}: {title}\n"
        f"{query}\n"
        "```\n\n"
    )

TARGET.write_text("".join(parts).rstrip() + "\n")
print(TARGET)
