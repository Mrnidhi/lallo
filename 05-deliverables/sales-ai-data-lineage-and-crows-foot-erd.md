# Sales AI Assistant — end-to-end data lineage and logical crow's-foot ERD

## Executive conclusion

The current Sales AI data estate can be traced from CSAL, DMSA, SharePoint, CRMI, and
application inputs into six gold and seven silver tables. The lineage is usable for production
documentation, but the physical relational contract is not production-complete: no primary-key,
unique-key, or foreign-key constraint was observed on the inspected targets, several joins use
names or agreement text, and `csm_csal_summary` does not retain `csal_id`, `booking_number`, or
`svvd`.

Consequently, the lineage diagram below shows transformation flow, while the separate
crow's-foot diagram shows only logical relationships. An ETL arrow must not be interpreted as a
database foreign key.

## Evidence legend

| Label | Meaning |
|---|---|
| `CODE` | Visible notebook SQL was inspected read-only. |
| `CATALOG` | Unity Catalog lineage or object metadata was observed on 2026-08-24. |
| `GENIE` | User-supplied Genie narrative from 2026-08-26; useful but not independently re-queried. |
| `SAMPLE` | A relationship or multiplicity is supported by the supplied extracts. |
| `SPEC` | Implementation or application specification was inspected; it is not proof of the live producer. |
| `INTENDED` | Specification, comment, or design intent only. |
| `UNKNOWN` | The producer, exact join, key, uniqueness, or multiplicity was not proven. |

Solid arrows in the lineage diagram represent code-, Catalog-, or sample-supported flow. Dotted
arrows are intended, contextual, or unresolved. Evidence labels are attached to the individual
edges.

## 1. End-to-end transformation lineage

![Sales AI end-to-end lineage](diagrams/sales-ai-end-to-end-lineage.svg)

Editable Mermaid source: [sales-ai-end-to-end-lineage.mmd](diagrams/sales-ai-end-to-end-lineage.mmd).

### Current table inventory

| Layer | Current objects in scope |
|---|---|
| CRMI curated | `dev.crmi_gold.csal_teu_performance` |
| Gold | `csm_csal_summary`, `fincon_issues`, `sales_ai_roster`, `sales_ai_case_ledger`, `sales_ai_case_issues`, `tea_deliverables` |
| Silver | `ar_daily_os`, `ar_weekly_os`, `mqc_expiry_report`, `tea_task_queue`, `tea_memory`, `tea_action_ledger`, `tea_capability_registry` |

All short gold/silver names in the diagrams are under `dev.sales_ai_assistant_gold` or
`dev.sales_ai_assistant_silver` respectively.

### Transformation edge registry

| # | Source | Target/process | Main transformation | Logical source-to-target behavior | Evidence |
|---:|---|---|---|---|---|
| 1 | `datasources.csal.csal_plan` | CSAL + shipment TEU build | Finalized Regular/Extra Protection plus qualifying unfinalized plans | One logical plan can produce zero-to-many joined booking rows | `CODE`; plan uniqueness `UNKNOWN` |
| 2 | `datasources.csal.csal_plan_no_csal` | CSAL + shipment TEU build | Latest non-archived and archived rows; independent `MAX` values grouped by `csal_id` | Many source rows to one plan aggregate, then zero-to-many bookings | `CODE` |
| 3 | `datasources.csal.csal_audit_trail` | CSAL + shipment TEU build | First/last finalize or reviewed-TEU event by CSAL plan | Many audit events to one audit aggregate | `CODE`; physical FK `UNKNOWN` |
| 4 | `datasources.csal.csal_sales_profile` | CSAL + shipment TEU build | Lower-cased username-to-sales-ID mapping | Intended one username to one identity; duplicates can fan out | `CODE` |
| 5 | `datasources.csal.csal_vessel_voyage` | CSAL + shipment TEU build | Constructs `svvd` with direction rules | Voyage rows to plan/SVVD mapping | `CODE`; multiplicity `UNKNOWN` |
| 6 | `datasources.csal.csal_voy_stop_dtl` | CSAL + shipment TEU build | Non-omitted departure stops; `MAX(sail_week)` and `MIN(tcr_cutoff)` by departure SVVD | Many stops to one departure-SVVD aggregate | `CODE` |
| 7 | `datasources.dmsa_dm_pb_shp.dmsa_pb_shp_mvmt` | CSAL + shipment TEU build | Status-specific TEU aggregation | Many movement rows to booking/status aggregate | `CODE`; movement grain `UNKNOWN` |
| 8 | `datasources.dmsa_dm_pb_shp.dmsa_pb_shp_shipment` | CSAL + shipment TEU build | Booking/customer/service/date context joined to movements | Shipment-to-movement multiplicity unresolved | `CODE` |
| 9 | CSAL + shipment TEU build | `dev.crmi_gold.csal_teu_performance` | Inner join on normalized agreement, customer, service, week, and SVVD with final two characters removed | Intended `csal_id + booking_number` grain; unmatched plans/bookings are dropped | `CODE`; uniqueness untested |
| 10 | `dev.crmi_gold.csal_teu_performance` | CSM build | Allocation aggregation and booking/status deduplication | Many source rows to summary allocation/category rows | `CODE + CATALOG` |
| 11 | `datasources.csal.csal_booking_detail` | CSM build | Shipment-number enrichment; reasons, ports, CY cutoff, booking lead time | Many details to booking-base aggregate, then one-to-many CSM rows | `CODE + CATALOG + SAMPLE` |
| 12 | Volume `docs/Expiry Report.xlsx` | `silver.mqc_expiry_report` | Workbook ingestion | Workbook-row cardinality and producer code unresolved | `INTENDED/CORROBORATED` |
| 13 | `silver.mqc_expiry_report` | CSM build | Filter `TPT_E`/`TAT_W`, aggregate by agreement | Many MQC rows to one agreement aggregate, then zero-to-many CSM rows | `CODE + CATALOG + SAMPLE` |
| 14 | `dev.crmi_gold.oocl_casereference_v` | CSM build | Agreement/contract references | Reference/case multiplicity unresolved | `CODE + CATALOG` |
| 15 | `dev.crmi_gold.incident_v` | CSM build | Select latest non-closed `(Monitoring) IB CSAL` incident per agreement | Many incidents to one selected incident, then zero-to-many CSM rows | `CODE + CATALOG` |
| 16 | `dev.crmi_gold.incidentresolution_v` | CSM build | Resolution enrichment | Intended zero-or-one resolution per selected incident | `CODE + CATALOG`; multiplicity `UNKNOWN` |
| 17 | CSM build | `gold.csm_csal_summary` | Materialize allocation, booking, rate, cutoff, issue, swap, CRM, and MQC fields | Candidate allocation/category summary grain; no enforced key | `CODE + CATALOG + SAMPLE` |
| 18 | SharePoint `Daily OS Report/Outstanding Report.CSV` | `silver.ar_daily_os` | Daily outstanding-balance ingestion | File rows to invoice/snapshot-like rows | `CATALOG`; exact grain `UNKNOWN` |
| 19 | `silver.ar_daily_os` | `gold.fincon_issues` | Latest snapshot, `OSAmt > 0`, normalize names, aggregate balance/aging by customer and sales | Many invoices to one customer/sales/snapshot aggregate | `SPEC + CATALOG`; live producer masked |
| 20 | `silver.ar_weekly_os` | UI/FinCon drill-down | Intended weekly detail | No live downstream table consumer observed | `INTENDED`; source and producer `UNKNOWN` |
| 21 | `dev.crmi_gold.account_v` + `systemuser_v` | Roster build | CRM account-owner branch | Many account assignments into roster assignment rows | `CATALOG`; exact join `UNKNOWN` |
| 22 | CSM + CRMI performance + FinCon | Roster build | Distinct CSM/booking and FinCon rep/customer assignment branches | Union into a name-based many-to-many assignment bridge | `CATALOG + GENIE`; exact producer SQL unresolved |
| 23 | Roster build | `gold.sales_ai_roster` | Effective-dated assignment materialization | Rep-to-customer association rows; no assignment ID/unique constraint | `GENIE + CATALOG`; many-to-many multiplicity `SAMPLE` |
| 24 | CSM + FinCon + active roster | `sales_ai_top10_refresh` | Normalize, score seven conditions, select up to ten customer keys per rep | Many signals to customer-level case candidates | `CODE + CATALOG` |
| 25 | `sales_ai_top10_refresh` | `gold.sales_ai_case_ledger` | Merge using `UPPER(customer_name)` as `natural_key` | Intended one current customer case; sample contains duplicate natural keys | `CODE + SAMPLE` |
| 26 | `sales_ai_top10_refresh` | `gold.sales_ai_case_issues` | Create and lifecycle-manage issue rows | One logical ledger case to zero-to-many issues | `CODE + SAMPLE`; no physical FK observed |
| 27 | Daily Outlook/ad-hoc/TCA | `silver.tea_task_queue` and `tea_memory` | Queue work and intended contextual memory | Flow inputs to task/context records | `SPEC + observed flow evidence`; exact producer mix varies |
| 28 | Queue + memory + capability registry | Agent task execution | Select task/context/capability, execute tools, update outcome | One task/run can generate zero-to-many execution outputs | `SPEC + SAMPLE` |
| 29 | Agent task execution | `gold.tea_deliverables` | Persist task deliverable | One task to zero-to-many deliverable versions logically | `SPEC + SAMPLE`; no physical FK observed |
| 30 | Agent task execution | `silver.tea_action_ledger` | Intended append-only action audit | One task/run to zero-to-many action steps | `INTENDED`; current writer explicitly absent |
| 31 | `gold.tea_deliverables` | Current UI/notifier | Intended delivery/notification | Current scheduled notifier reads legacy personal-schema objects instead | `INTENDED`; bridge unobserved |

## 2. Logical crow's-foot ERD

![Sales AI logical crow's-foot ERD](diagrams/sales-ai-crows-foot-erd.svg)

Editable Mermaid source: [sales-ai-crows-foot-erd.mmd](diagrams/sales-ai-crows-foot-erd.mmd).

### Cardinality notation

| Symbol | Meaning |
|---|---|
| `||` | Exactly one |
| `o|` | Zero or one |
| `|{` | One or many |
| `o{` | Zero or many |

The ERD is logical, not a declaration of implemented constraints. `SALES_REP`, `CUSTOMER`,
`BOOKING_BASE`, `AGREEMENT_AGGREGATE`, `CRM_SELECTED_INCIDENT`, and
`AR_DAILY_INCLUDED_INVOICE` are
conceptual entities used to express the observed grain and cardinality; they are not claimed to
be physical tables in the Sales AI schemas.

### Relationship interpretation

| Relationship | Interpretation | Confidence / limitation |
|---|---|---|
| Sales rep to roster | One conceptual rep can have zero-to-many effective-dated assignment rows | Sample supports; governed rep dimension/ID not present in this schema |
| Customer to roster | One conceptual customer can have zero-to-many assignment rows | Sample shows customer-to-multiple-active-rep cases; name is not a governed ID |
| Customer to case ledger | One customer can have zero-to-many case rows in the current physical data | Intended current maximum is one, but the sample violates customer-key uniqueness |
| Ledger to case issues | One case logically owns zero-to-many issue rows; an issue belongs to one case | Logical `case_id`, sample-supported; no physical FK observed |
| Ledger prior-case self-link | A case can optionally reference a prior case | Intended only; all sampled `prior_case_id` values are null |
| Booking base to CSM | One `(customer, agreement, service, week_num)` booking aggregate can fan out across allocation/category rows | Sample-supported; booking measures must be counted once per booking base |
| Agreement aggregate to CSM | A CSM row has zero-or-one matching MQC aggregate; one agreement aggregate can repeat across zero-to-many CSM rows | Code- and sample-supported; agreement uniqueness not governed |
| Selected CRM incident to CSM | A CSM row has zero-or-one selected matching incident; one incident can repeat across zero-to-many CSM rows | Code- and sample-supported; not related to ledger `case_id` |
| Included daily AR invoice to FinCon | One-or-many qualifying latest-snapshot invoice rows aggregate into one customer/sales/snapshot issue row; each included row belongs to one such aggregate | Logical grain; exact target uniqueness under multiple assignments unresolved |
| Task to deliverables | One task can logically have zero-to-many deliverable versions | Sample-supported; at most one current version appears in sample, not constrained |
| Task to action ledger | One task/run is intended to have zero-to-many action steps | Design-only; active writer not proven |

## 3. Critical production boundaries

1. **Vessel identity is lost in the CSM gold table.** `svvd` is available upstream in
   `dev.crmi_gold.csal_teu_performance`, but `csm_csal_summary` does not retain it. `service +
   week` is not proven to identify one vessel. A vessel-level swap recommender must preserve or
   rejoin a canonical `vessel_voyage_id`/`svvd`.
2. **The CSM display grain is not an enforced row identity.** The candidate nine-field display
   key is unique in the supplied sample, but `csal_id` and booking number are dropped. Booking,
   MQC, and CRM context repeat across allocation/category rows.
3. **Source measures can be multiplied by fan-out.** The sample has two repeated booking bases.
   Naive aggregation overstates booked TEU by 78, confirmed by 28, rejected by 38, cancelled by
   0, no-show by 12, booking count by 6, and total booking count by 14.
4. **Roster is a many-to-many association.** Rep/customer names are logical matching fields,
   not canonical identities. Name-only joins can multiply CSM or FinCon rows.
5. **Case identity has two separate meanings.** `csm_csal_summary.case_incidentid` is a CRMI
   monitoring incident. It must not be joined to `sales_ai_case_ledger.case_id`.
6. **Ledger uniqueness is not enforced.** The observed merge key is uppercase customer name;
   five sampled natural keys have two case rows.
7. **Weekly AR is isolated.** `ar_weekly_os` exists, but no live downstream table lineage was
   observed. It is shown only as intended UI/drill-down input.
8. **TEA lineage has two breaks.** The current design does not write `tea_action_ledger`, and the
   scheduled notifier reads legacy personal-schema deliverables rather than the current gold
   table.

## 4. Production data-contract changes required for vessel swap scoring

| Contract change | Why it is required |
|---|---|
| Preserve `csal_id`, `booking_number`, `svvd`, and a canonical `vessel_voyage_id` from CRMI into the scoring mart | Establish allocation, booking, and physical sailing identity; prevent service/week proxy matching |
| Add governed `customer_id`, `sales_rep_id`, and `agreement_id` | Replace name-based joins and control roster fan-out |
| Store `source_snapshot_ts`, producer-run ID, Delta version, and rule version | Make cutoff, freshness, and recommendation reproduction auditable |
| Separate allocation facts, booking facts, agreement context, and incident context before scoring | Prevent repeated booking/MQC/CRM measures from being summed at allocation/category grain |
| Materialize donor, receiver, and candidate-edge IDs | Enforce no self-match, edge uniqueness, and capacity conservation |
| Retain route-leg, cutoff timestamp/timezone, equipment, weight, reefer, dangerous-goods, and policy compatibility fields | Make a recommendation physically and commercially executable |
| Add recommendation/reservation/outcome ledgers with immutable IDs | Prevent double allocation and provide labels for calibration and monitoring |
| Add executable uniqueness, not-null, referential, reconciliation, and freshness expectations | Convert the logical ERD into an enforceable production contract |

Until these are present, `csm_csal_summary` supports portfolio risk analysis and service/week
opportunity screening; it does not independently support a safe vessel-level donor/receiver
recommendation.

## 5. Evidence references

- [Canonical Sales AI data lineage](../02-knowledge/systems/sales-ai-data-lineage.md)
- [2026-08-24 raw code-and-data audit](../03-projects/sales-agent/materials/2026-08-24__sales-ai-gold-silver-code-audit/raw.md)
- [2026-08-26 gold/silver lineage capture](../03-projects/sales-agent/materials/2026-08-26__gold-silver-lineage-capture/)
- [CSM table documentation](../02-knowledge/systems/databricks-tables/dev-sales-ai-assistant-gold-csm-csal-summary.md)
- [CRMI CSAL TEU performance documentation](../02-knowledge/systems/databricks-tables/dev-crmi-gold-csal-teu-performance.md)
