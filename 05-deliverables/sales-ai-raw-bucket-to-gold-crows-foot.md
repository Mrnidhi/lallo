# Sales AI Assistant — raw/bucket to Gold crow's-foot lineage

## Scope and evidence boundary

This package maps every currently inventoried Sales AI Silver and Gold table from the
locally retained evidence captured through 2026-08-27. It also includes the directly
observed raw/domain inputs, Volume/file boundaries, the cross-domain CRMI curated table,
and the logical serving relationships.

No live OOCL system was opened and no notebook, job, or query was run for this deliverable.

There is **no observed Bronze table layer** in the captured implementation. The current
pattern is:

```text
datasources.* raw/domain tables or Unity Catalog Volume files
    -> dev.crmi_gold.csal_teu_performance and/or Sales AI Silver
    -> Sales AI Gold summaries and assignment/case tables
    -> Sales AI Silver task queue
    -> Sales AI Gold deliverables
```

The crow's-foot lines are **logical transformation or row-contract relationships**. They
are not claims that physical primary keys or foreign keys exist. No PK, FK, unique, or
not-null enforcement was verified on the inspected Sales AI targets.

## Evidence and cardinality legend

| Mark | Meaning |
|---|---|
| `||` | Exactly one |
| `o|` | Zero or one |
| `|{` | One or many |
| `o{` | Zero or many |
| `[CODE]` | Current notebook SQL join, aggregation, read, or write was inspected |
| `[CAT]` | Unity Catalog lineage was observed; producer code may be masked |
| `[SAMPLE]` | Multiplicity is supported by a retained local sample |
| `[SPEC]` | Specification or historical implementation logic; not proof of the current producer |
| `[INT]` | Intended/comment-defined relationship only |
| `[UNKNOWN]` | Producer or relationship is unresolved |
| `[CARD?]` | The edge is observed, but source-key uniqueness or exact multiplicity is unproven |

## Master physical-object crow's-foot

This master view contains all 13 current Sales AI target tables, the CRMI CSAL curated
table, all current-code raw/domain inputs, and the three file-source boundaries. Because it
is intentionally exhaustive, use the SVG for lossless zoom and the branch diagrams below
for everyday reading.

![Master raw/bucket-to-Gold crow's-foot](diagrams/sales-ai-raw-bucket-to-gold-crows-foot.svg)

- [Editable Mermaid source](diagrams/sales-ai-raw-bucket-to-gold-crows-foot.mmd)
- [SVG](diagrams/sales-ai-raw-bucket-to-gold-crows-foot.svg)
- [PNG](diagrams/sales-ai-raw-bucket-to-gold-crows-foot.png)

## Branch 1 — CSAL and DIMSA raw data to CSM Gold

![CSAL to CSM crow's-foot](diagrams/sales-ai-csal-to-csm-crows-foot.svg)

- [Editable Mermaid source](diagrams/sales-ai-csal-to-csm-crows-foot.mmd)
- [SVG](diagrams/sales-ai-csal-to-csm-crows-foot.svg)
- [PNG](diagrams/sales-ai-csal-to-csm-crows-foot.png)

The conceptual aggregate entities in this branch are named as logical CTEs. They are shown
to express the actual row-grain transitions without pretending that a raw ETL arrow is a
foreign key:

- plan and audit rows establish CSAL allocation history;
- shipment and movement rows become a booking/status TEU aggregate;
- plan and booking aggregates combine into `dev.crmi_gold.csal_teu_performance`;
- allocation aggregation drives the CSM output rows;
- the booking aggregate is optional and can repeat across allocation/category rows;
- MQC and the selected CRM incident are agreement-level context repeated on CSM rows.

## Branch 2 — Volume/files to AR and MQC Silver, then Gold

![Files, Finance, and MQC crow's-foot](diagrams/sales-ai-files-finance-mqc-crows-foot.svg)

- [Editable Mermaid source](diagrams/sales-ai-files-finance-mqc-crows-foot.mmd)
- [SVG](diagrams/sales-ai-files-finance-mqc-crows-foot.svg)
- [PNG](diagrams/sales-ai-files-finance-mqc-crows-foot.png)

`ar_weekly_os` is deliberately shown with no downstream target: no verified current table
consumer was observed. The `Expiry Report.xlsx` edge is intended/corroborated rather than a
current-code producer edge because the ingestion producer is masked.

## Branch 3 — CRM/CSAL/CSM/FinCon to roster, cases, and issues

![Roster and case crow's-foot](diagrams/sales-ai-roster-case-crows-foot.svg)

- [Editable Mermaid source](diagrams/sales-ai-roster-case-crows-foot.mmd)
- [SVG](diagrams/sales-ai-roster-case-crows-foot.svg)
- [PNG](diagrams/sales-ai-roster-case-crows-foot.png)

The roster is a many-to-many representative/customer assignment association. Most
roster-to-case and signal-to-case lines are process transformations, not persisted row FKs.
The strongest current logical row contract is:

```text
sales_ai_case_ledger ||--o{ sales_ai_case_issues
```

The CSM field `case_incidentid` is a CRMI monitoring incident and must never be treated as
`sales_ai_case_ledger.case_id`.

## Branch 4 — Gold context to TEA Silver and final Gold deliverables

![TEA serving crow's-foot](diagrams/sales-ai-tea-serving-crows-foot.svg)

- [Editable Mermaid source](diagrams/sales-ai-tea-serving-crows-foot.mmd)
- [SVG](diagrams/sales-ai-tea-serving-crows-foot.svg)
- [PNG](diagrams/sales-ai-tea-serving-crows-foot.png)

`tea_memory` and `tea_capability_registry` are standalone intentionally. They exist, but no
stable row-level FK to another current table was verified. Queue-to-deliverable is a logical
`task_id` contract; the application writer remains unresolved. Queue-to-action is intended,
and the current action-ledger writer was not verified.

## Complete current target-table inventory

### Sales AI Silver — seven tables

| Table | Immediate upstream | Current observed or intended downstream | Evidence status |
|---|---|---|---|
| `dev.sales_ai_assistant_silver.ar_daily_os` | Daily OS SharePoint/Volume CSV | `gold.fincon_issues` | File edge and Gold edge are Catalog-observed; producer SQL masked |
| `dev.sales_ai_assistant_silver.ar_weekly_os` | Unknown weekly AR extract | No verified table consumer | Producer job/notebook masked |
| `dev.sales_ai_assistant_silver.mqc_expiry_report` | `Expiry Report.xlsx` | `gold.csm_csal_summary` | Workbook edge intended/corroborated; Silver-to-Gold current-code verified |
| `dev.sales_ai_assistant_silver.tea_task_queue` | Daily, SPACE_SWAP, and ad-hoc runners | Task-execution app and `gold.tea_deliverables` logical contract | Runner inserts/reads verified; app mutations unresolved |
| `dev.sales_ai_assistant_silver.tea_memory` | DDL/bootstrap; population unresolved | Intended agent context | No verified operational writer or row FK |
| `dev.sales_ai_assistant_silver.tea_action_ledger` | DDL/bootstrap | Intended execution audit | Current operational writer absent/unverified |
| `dev.sales_ai_assistant_silver.tea_capability_registry` | DDL/bootstrap and seed rows | Intended runtime capability discovery | Runtime read not captured |

### Sales AI Gold — six tables

| Table | Immediate upstream | Main observed downstream | Evidence status |
|---|---|---|---|
| `dev.sales_ai_assistant_gold.csm_csal_summary` | CRMI performance, booking detail, three CRM views, MQC Silver | Roster, top-10 cases/issues, SPACE_SWAP runners | Current producer code verified |
| `dev.sales_ai_assistant_gold.fincon_issues` | `silver.ar_daily_os` | Roster and top-10 cases/issues | Catalog edge observed; producer SQL masked |
| `dev.sales_ai_assistant_gold.sales_ai_roster` | CRMI account/user, CRMI performance, CSM, FinCon | Top-10 and runner representative resolution | Catalog inputs observed; producer SQL masked |
| `dev.sales_ai_assistant_gold.sales_ai_case_ledger` | Top-10 refresh from CSM, FinCon, and roster | Child issues and Daily/ad-hoc runner targeting | Current mutations and reads verified |
| `dev.sales_ai_assistant_gold.sales_ai_case_issues` | Top-10 refresh | Case/UI lifecycle and refresh self-read | Current mutations verified with bounded source gaps |
| `dev.sales_ai_assistant_gold.tea_deliverables` | Intended task-execution app writer | Ad-hoc and production SPACE_SWAP reads | Target/read behavior observed; app writer unresolved |

### Cross-domain curated intermediate

| Table | Upstream | Downstream |
|---|---|---|
| `dev.crmi_gold.csal_teu_performance` | Ten raw/domain objects listed below | CSM Gold and roster Gold |

## Complete raw/domain and file-source inventory

### Current-code raw inputs to `csal_teu_performance`

1. `datasources.csal.csal_sales_profile`
2. `datasources.csal.csal_plan`
3. `datasources.csal.csal_audit_trail`
4. `datasources.csal.csal_plan_no_csal`
5. `datasources.csal.csal_vessel_voyage`
6. `datasources.csal.csal_voy_stop_dtl`
7. `datasources.csal.cor_year_month_week`
8. `datasources.dimsa_dm_pb_shp.dimsa_pb_shp_mvmt`
9. `datasources.dimsa_dm_pb_shp.dimsa_pb_shp_shipment`
10. `datasources.cisp.org_flattn_hierarchy`

### Other direct source tables/views

1. `datasources.csal.csal_booking_detail` -> CSM Gold
2. `dev.crmi_gold.oocl_casereference_v` -> CSM Gold
3. `dev.crmi_gold.incident_v` -> CSM Gold
4. `dev.crmi_gold.incidentresolution_v` -> CSM Gold
5. `dev.crmi_gold.account_v` -> roster Gold
6. `dev.crmi_gold.systemuser_v` -> roster Gold

### Volume/file boundaries

1. `/Volumes/datasources/sharepoint/fincon/Daily OS Report/Outstanding Report.CSV`
   -> `silver.ar_daily_os`
2. unresolved weekly AR extract -> `silver.ar_weekly_os`
3. `/Volumes/dev/sales_ai_assistant_silver/docs/Expiry Report.xlsx`
   -> `silver.mqc_expiry_report`

## Transformation edge register

| Source population | Target | Logical behavior | Evidence and caveat |
|---|---|---|---|
| CSAL plan | CSAL audit trail | One logical plan to zero-or-many audit events by `csal_id` | `[CODE]`; physical FK not verified |
| CSAL plan/no-CSAL, sales profile, voyage, stop, calendar | CRMI performance | Optional mapping/normalization branches feeding many result rows | `[CODE][CARD?]` |
| DIMSA shipment + movement + org hierarchy | CRMI performance | Shipment/movement join, TCR mapping, booking-status TEU aggregation | `[CODE][CARD?]`; source uniqueness untested |
| CRMI performance | CSM Gold | Allocation aggregation plus booking aggregation and fan-out | `[CODE][CARD?]`; no enforced output key |
| Booking detail | CSM Gold | Aggregated reasons/ports/cutoff/lead-time copied to allocation rows | `[CODE][CARD?]` |
| Three CRMI case views | CSM Gold | Latest active incident selected by agreement and repeated | `[CODE][CARD?]` |
| MQC Silver | CSM Gold | Trade-bound filter, agreement aggregate, repeated context | `[CODE]` |
| Daily OS file | AR Daily Silver | File rows ingested into an invoice/snapshot-like table | `[CAT]`; producer masked |
| AR Daily Silver | FinCon Gold | Latest positive-balance rows aggregated by customer/sales/snapshot | `[CAT][SPEC]`; current SQL masked |
| Weekly AR source | AR Weekly Silver | Ingestion relationship only | `[UNKNOWN]` |
| Expiry workbook | MQC Silver | Workbook ingestion relationship | `[INT]`; producer masked |
| CRMI account/user + performance + CSM + FinCon | Roster Gold | Unioned ownership/assignment branches | `[CAT][CARD?]`; precedence and exact join masked |
| CSM + FinCon + active roster | Case ledger/issues | Score, rank, merge, insert, update, and resolve | `[CODE]`; process lineage, not source-row FK |
| Case ledger | Case issues | One logical case may own zero-or-many issue rows by `case_id` | `[CODE][SAMPLE]`; no physical FK observed |
| Case ledger/roster/CSM | TEA task queue | Representative-scoped tasks inserted by runners | `[CODE]`; process lineage |
| TEA task queue | Gold deliverables | One logical task may have zero-or-many deliverable versions | `[INT][SAMPLE]`; writer and current-version rule not enforced |
| TEA task queue | TEA action ledger | Intended one task to zero-or-many action steps | `[INT]`; operational writer absent/unverified |

## Production-critical boundaries

1. **No Bronze layer was observed.** Do not label `datasources.*` or Volume files as Bronze
   unless a real Bronze contract is later found.
2. **No physical relational constraints were verified.** Crow's feet describe safe logical
   multiplicity, not implemented PK/FK enforcement.
3. **Current shipment spelling is `dimsa_*`.** Older retained evidence uses `dmsa_*`; this is
   a source-version naming conflict, not two proven parallel sources.
4. **CSM loses vessel-level identity.** `csal_id`, `booking_number`, and `svvd` exist upstream
   but are not retained in the 63-column Catalog/sample CSM view. `service + week` is not a
   proven vessel key.
5. **CSM schema evidence conflicts.** The captured producer DDL declares 78 columns while the
   dated Catalog/sample artifact has 63. The currently published schema revision remains
   unresolved.
6. **Booking, MQC, and CRM context fan out.** They can repeat across CSM allocation/category
   rows and must not be naively summed.
7. **Roster is many-to-many and name-based.** A customer can have multiple active reps; there
   is no governed customer/rep key in the current Sales AI contract.
8. **CRM incident and Sales AI case IDs are different identities.** Never join
   `csm_csal_summary.case_incidentid` to `sales_ai_case_ledger.case_id`.
9. **The final notifier path is split.** The scheduled notifier reads legacy personal-schema
   deliverables/roster objects; no replication bridge from current Gold deliverables was
   observed.
10. **The proposed `swap_opportunity` is not shown as current.** No physical table currently
    exists. It should be added only after its grain, vessel-voyage identity, reservation, and
    event contracts are approved and implemented.

## Historical or validation-only objects excluded from the current ERD

The following are intentionally excluded from the main current-state diagram because they
are historical, inert, validation-only, or legacy-serving objects rather than current target
lineage:

- `dev.sales_ai_assistant_silver.csal_data`
- `dev.sales_ai_assistant_silver.ib_shp_tracker_v`
- `dev.crmi_gold.finalized_ib_csal_teu_v`
- `dev.crmi_gold.oocl_agreement_v` when used only by analysis cells
- `usr.cadigje.*`
- `usr.madabra.*`
- `usr.flamezi2.csm_customer_mqc_fulfillment`
- legacy notifier inputs `usr.flamezi2.tea_deliverables` and
  `usr.flamezi2.sales_ai_rep_roster`

The last two remain operationally relevant to the legacy notifier break, but they are not
part of the current six-Gold/seven-Silver target model.
