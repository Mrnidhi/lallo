# Sales AI V3: Full Gold Normalization and Three-Way Agent Test

## What V3 is meant to prove

V3 will test whether a cleaner data foundation helps Sales AI agents answer more accurately and consistently without changing production.

The scope is the complete Sales AI Gold dataset, not only the CSM/CSAL table. We will use a controlled one-month sample in the personal workspace and compare three ways of serving the same information:

1. The current Gold structure.
2. Normalized facts, dimensions and bridges.
3. Small domain views built on the normalized model.

The same verified business questions will be asked in all three setups. We will compare correctness, reliability, SQL complexity and speed. Production remains read-only throughout the work.

## Decision summary

The recommended design is:

```text
Current Gold sources
        |
        v
Complete source inventory and frozen one-month sample
        |
        v
Facts, dimensions and relationship bridges
        |
        v
Small, grain-safe domain views
        |
        +--------------------------+
        |                          |
        v                          v
Flexible Genie queries       Narrow UC functions
        |                          |
        +-------------+------------+
                      v
              Specialist agents
                      |
                      v
                 Central agent
```

Facts and dimensions provide the governed foundation. Curated views are normally the best interface for Genie because they remove unnecessary joins and expose only the fields needed for a business area. UC functions are kept only for narrow, repeatable operations where a normal view and reviewed SQL example are not enough.

This is a proposal for a personal V3 proof of concept. It is not approval to replace the production model.

## Verified current scope

The latest locally captured producer definitions show six tables in `dev.sales_ai_assistant_gold`. Their captured schemas contain 180 columns in total.

| Current Gold table | Captured columns | What it currently represents |
|---|---:|---|
| `dev.sales_ai_assistant_gold.csm_csal_summary` | 78 | CSM allocation, commitment, booking, MQC, risk, CRM and swap-screening information in one wide result |
| `dev.sales_ai_assistant_gold.fincon_issues` | 11 | Customer accounts-receivable position by snapshot and sales context |
| `dev.sales_ai_assistant_gold.sales_ai_roster` | 9 | Effective-dated customer and sales-representative assignments |
| `dev.sales_ai_assistant_gold.sales_ai_case_ledger` | 41 | Current Sales AI case state and recommendation context |
| `dev.sales_ai_assistant_gold.sales_ai_case_issues` | 30 | Issue records belonging to Sales AI cases |
| `dev.sales_ai_assistant_gold.tea_deliverables` | 11 | Versioned task-execution outputs and their payloads |

One additional Gold table is an important upstream CSM/booking source:

| Upstream Gold table | Captured columns | Role in V3 |
|---|---:|---|
| `dev.crmi_gold.csal_teu_performance` | 31 | Supplies booking, allocation and sailing detail used by the CSM domain; it is a reconciliation and modeling source, not a new Sales AI Gold contract by default |

The older documentation captured 63 columns for `csm_csal_summary` and 29 for `csal_teu_performance`. This is evidence of schema change, not a reason to choose one count. The first V3 step must read the live schemas in Databricks, record the Delta versions and create the final source manifest. No table or column count will be hard-coded into the build.

## What is wrong with treating the current Gold set as one simple model

The tables are not all badly designed. They represent different business processes:

- `fincon_issues` is already close to a customer and snapshot fact.
- `sales_ai_roster` is naturally a many-to-many assignment bridge.
- `sales_ai_case_ledger` and `sales_ai_case_issues` are a parent and child process.
- `tea_deliverables` is naturally a deliverable-version fact.
- `csm_csal_summary` is the main mixed-grain table. Booking, allocation, commitment, MQC, monthly, CRM and swap values can repeat at different levels in the same output.

The correct V3 approach is therefore not to split every table in the same way. It is to preserve each valid business grain and separate only the processes that are currently mixed.

No physical primary key, foreign key or uniqueness constraint has been verified on this Gold set. V3 will treat candidate keys as logical contracts and prove them with tests before relying on them.

## Target V3 model

### Shared dimensions

| Proposed object | Purpose |
|---|---|
| `dim_date` | One governed calendar for reporting date, planning week, sailing week and snapshot roles |
| `dim_customer` | Stable customer identity and approved descriptive attributes |
| `bridge_customer_alias` | Maps source-specific customer names to a governed customer where a trusted common ID is unavailable |
| `dim_sales_rep` | Sales representative identity and stable attributes |
| `dim_agreement` | Agreement identity and descriptors |
| `dim_service` | Service or service-loop identity |
| `dim_tcr` | TCR identity and description |
| `dim_csal_category` | CSAL allocation category |
| `dim_sailing` | Vessel and voyage identity after the source key is verified |
| `dim_location` | Port and final-destination identity, used in POL, POD and FND roles |
| `dim_booking_status` | Governed booking-status values |
| `dim_booking_reason` | Rejection and cancellation reason values |
| `dim_issue_type` | Sales AI issue type and description |
| `dim_task_type` | Task and deliverable type definitions |
| `dim_agent_config` | Versioned agent or execution configuration used to produce an output |
| `dim_metric_policy` | Versioned definition of a metric, denominator, flag and threshold policy |

We will use a historical dimension only when the source actually provides meaningful history. A current snapshot will never be expanded into invented historical records.

### Facts and bridges

| Proposed object | Exact logical grain | Main source |
|---|---|---|
| `fact_csal_allocation_snapshot` | One frozen snapshot and one CSAL allocation scope | CSM plus CRMI CSAL performance |
| `fact_booking_snapshot` | One frozen snapshot and one booking number | CRMI CSAL performance |
| `fact_booking_status_snapshot` | One frozen snapshot, booking number and booking status | CRMI CSAL performance |
| `bridge_booking_allocation_match` | One frozen snapshot, booking, allocation and match version | CRMI CSAL performance |
| `fact_csal_commitment_snapshot` | One frozen snapshot, customer, agreement, planning week and service | CSM |
| `fact_csm_monthly_performance` | One frozen snapshot, month, customer, sales representative, agreement and service | CSM monthly fields |
| `fact_mqc_agreement_snapshot` | One frozen snapshot, agreement and source reporting context | CSM and verified MQC source |
| `fact_crm_incident_snapshot` | One frozen snapshot and one CRM incident | CSM CRM fields |
| `bridge_agreement_crm_incident` | One agreement, CRM incident and effective interval | CSM CRM context |
| `fact_csm_risk_signal_snapshot` | One snapshot, commercial scope, signal type and metric-policy version | CSM flags and scores |
| `fact_swap_screen_snapshot` | One snapshot and one commercial allocation scope | CSM swap-screening fields |
| `fact_ar_customer_snapshot` | One customer and one AR snapshot date, with sales context retained | FinCon |
| `bridge_customer_sales_rep_assignment` | One customer, sales representative, assignment source and effective interval | Roster |
| `fact_sales_case_snapshot` | One frozen snapshot and one `case_id` | Case ledger |
| `fact_sales_case_issue_snapshot` | One frozen snapshot and one `case_issue_id` | Case issues |
| `bridge_case_category` | One case and one category value | Case ledger |
| `bridge_case_source_agent` | One case and one contributing source-agent value | Case ledger |
| `bridge_case_recurrence` | One current case and one prior case | Case ledger |
| `fact_tea_deliverable_version` | One frozen snapshot and one `deliverable_id` | TEA deliverables |

These names are V3 design names. Final physical keys and grains must be confirmed from the frozen data before creation.

### Important modeling rules

- Allocation and booking TEU are summed only inside compatible grains.
- `total_reviewed_teu` is represented once at customer, agreement, week and service grain.
- Percentages and rates are recalculated from their numerator and denominator. They are never averaged.
- MQC values remain at agreement-level snapshot grain and are not multiplied by weekly joins.
- AR balances are snapshot values and are not summed across dates.
- The FinCon 30, 60 and 90-day fields are cumulative aging bands and are not added together.
- Roster ownership belongs in the effective-dated bridge, not inside `dim_customer`.
- `case_incidentid` from CRM is not the same key as `case_id` in the Sales AI case ledger.
- Case-ledger rows are not deduplicated only by `natural_key`. Saved evidence contains repeated natural keys with different case IDs.
- The raw TEA `payload` is preserved exactly, with a hash, even when it is invalid JSON. Parsed fields are optional children and do not replace the source payload.
- The current swap fields remain a screening signal. They are not presented as reservable capacity, a probability or an executable recommendation.
- Current hard-coded flags remain unchanged during the architecture benchmark. Distribution and quartile analysis is a separate experiment because changing both structure and business rules would make the result impossible to interpret.

## Curated views for Genie

The normalized model keeps all information, but Genie should not have to discover every join and grain for every question. These small views give each specialist a clear business contract.

| Proposed view | Intended grain and use |
|---|---|
| `agent_csm_booking_month_v3` | One customer, agreement, planning week and service booking scope for booking, cancellation and rejection questions |
| `agent_csm_allocation_month_v3` | One CSAL allocation scope for allocation and fulfillment questions |
| `agent_csm_mqc_month_v3` | One agreement and reporting context for MQC questions |
| `agent_csm_swap_screen_month_v3` | One screened donor or receiver scope; informational only |
| `agent_fincon_customer_month_v3` | One customer and AR snapshot date for outstanding and aging questions |
| `agent_case_current_v3` | One Sales AI case for case-state and recommendation questions |
| `agent_case_issue_current_v3` | One case issue for issue-detail and lifecycle questions |
| `agent_roster_asof_v3` | One effective customer and sales-representative assignment for the selected period |
| `agent_deliverable_current_v3` | One current deliverable version per task where the source contract permits it |

Each view will have:

- one declared grain;
- clear and stable column names;
- documented numerator and denominator rules;
- a source snapshot timestamp;
- a metric-policy version;
- only the fields needed by that domain;
- no agent-side join where the answer can be safely prepared in the view.

A smaller view is not data loss. The full normalized model retains all source information. The view is a focused menu for one specialist, while the kitchen still contains the complete dataset.

## Compatibility views and proof of no data loss

V3 will create one source-shaped compatibility view for every Sales AI Gold table:

- `compat_csm_csal_summary_v3`
- `compat_fincon_issues_v3`
- `compat_sales_ai_roster_v3`
- `compat_sales_ai_case_ledger_v3`
- `compat_sales_ai_case_issues_v3`
- `compat_tea_deliverables_v3`

Each compatibility view must reproduce every original column name, value, null and duplicate row in the selected frozen sample. These views are for reconciliation and backwards-compatibility testing. They are not the preferred Genie interface.

Before an agent test begins, all of the following must pass:

1. Every current source column is in the column coverage register.
2. Every column maps to a fact, dimension, bridge, derived view, technical field, preserved payload or an explicitly approved exclusion.
3. The original source and reconstructed compatibility view match as multisets in both directions.
4. Row counts, duplicate counts, data types, scales, time zones and null counts match.
5. Deterministic full-row hashes match after only documented numeric and timestamp normalization.
6. Additive measures reconcile at their declared business grains.
7. Every fact key is unique at its declared grain.
8. Every relationship has zero unexplained orphan keys.
9. Join tests show no unexpected row multiplication.
10. Existing flags and scores match the frozen source values.
11. FinCon aging values reconcile without adding cumulative buckets.
12. Roster overlap and active-assignment exceptions are reported, not silently removed.
13. Case and issue parent relationships are preserved.
14. TEA payload bytes or hashes and task version chains are preserved.

If a source contains a defect, V3 records it and preserves enough lineage to reconstruct the source. It does not silently clean the defect and then call the result lossless.

The correct claim, after the gates pass, is: **lossless for the selected frozen V3 sample**. One month cannot prove that all source history exists or that production is lossless.

## One-month sample design

We will select the most recent fully closed business month only after profiling the available dates. The month uses a fixed start, exclusive end and time zone. One date filter cannot be applied to every table because the tables represent different processes.

| Table or domain | V3 selection rule |
|---|---|
| CSM summary | Use the approved planning month and governed week mapping. Keep `week_num` and `sail_week` as different concepts. |
| CRMI CSAL performance | Use the rows supporting the selected CSM weeks and pin an explicit Delta version. Do not treat `run_date` as the only business date. |
| FinCon | Use `snapshot_date` values inside the month. If Gold contains only the latest snapshot, label it as an as-of snapshot instead of claiming one month of AR history. |
| Roster | Include assignments whose effective interval overlaps the month, plus assignments referenced by selected facts. |
| Case ledger | Keep parent cases referenced by selected issues and cases with relevant lifecycle activity. Current rows cannot recreate historical state. |
| Case issues | Include issues generated, active, resolved or cleared during the month, with their parent cases. |
| TEA deliverables | Use versions created in the month and include the complete task-version chain needed to test `is_current`. |

Relationship rows outside the date window receive a reason such as `AS_OF_DIMENSION`, `PARENT_CLOSURE` or `VERSION_CHAIN_CLOSURE`. This makes every extra row explainable.

The source manifest will record:

- V3 run and sample IDs;
- source table and Delta version;
- commit timestamp;
- business-date selection rule;
- row and column counts;
- schema fingerprint;
- data or measure hashes where feasible;
- earliest and latest relevant dates;
- known limitation or deviation.

## Unity Catalog functions and Genie

### What a UC function is doing here

A Unity Catalog function gives an agent a controlled operation with named inputs and a fixed result contract. It is useful when the same narrow calculation or lookup must be applied consistently. It is not automatically better than querying a clean view.

Genie should query a curated view directly for normal questions such as:

- show customers with high cancellation in the selected month;
- list the lowest fulfillment results for a sales representative;
- summarize outstanding balances by customer;
- show open cases for a representative;
- find current deliverables for a task.

A UC function may be useful when:

- the operation has parameters and must always return one governed shape;
- the logic is reused by several agents;
- a deterministic rule must be versioned and applied identically;
- the capability cannot be expressed safely through a view and reviewed SQL example;
- access must be limited to a narrow operation instead of a broad table.

A function should not be used only to hide an unclear grain, duplicate stale logic, call another model unnecessarily or give one benchmark arm an unfair shortcut.

### Functions found in the saved CSM agent configuration

The dated CSM configuration showed these six functions:

| Function | Saved purpose or behavior | V3 concern |
|---|---|---|
| `usr.flamezi2.get_rep_csal_summary` | Returns representative-level CSAL issues | Reads legacy personal tables and uses fixed risk rules that have drifted from current Gold |
| `usr.flamezi2.get_csal_detail` | Returns CSAL TEU detail | Uses a different utilization denominator from `get_csm_history` |
| `usr.flamezi2.calculate_severity` | Calculates severity | Stored function and current refresh logic were observed to differ |
| `usr.flamezi2.get_booking_rejection_cancellation_reasons` | Returns booking rejection and cancellation details | Reads the old booking tracker and uses inconsistent optional-parameter behavior |
| `usr.flamezi2.get_customer_mqc_fulfillment` | Returns customer MQC fulfillment | Uses status logic that does not match the current Gold summary |
| `usr.flamezi2.get_csm_history` | Returns older closed CSM incident information | Reads legacy case and TEU tables and uses a different utilization formula |

The saved audit also found broader function families:

| Domain | Examples observed in documentation | V3 treatment |
|---|---|---|
| FinCon | `get_rep_ar_summary`, `get_invoice_detail`, `get_fincon_ar_history` | Inventory source, parameters and freshness; rebuild only if a direct view cannot satisfy the verified question |
| Cases | `get_case_details_by_customer`, `get_rep_open_cases`, `get_rep_closed_cases`, `get_rep_open_issues`, `get_rep_day_outlook_cases` | Point read-only versions to curated case views only after parent-child and state rules pass |
| Analysis and narrative | `generate_ai_recommendation`, `analyze_issue`, `analyze_case`, `analyze_rep`, `analyze_rsm`, `analyze_vp`, `generate_day_outlook_narrative` | Keep outside deterministic data benchmark because they call models and can produce nondeterministic output |
| Swap and booking action support | `find_swap_space`, `get_blocked_booking_detail` | Do not carry forward as-is; saved audit found cutoff, service-loop and selection-rule gaps |
| Task execution | `tea_create_task`, `tea_get_pending_tasks`, `tea_disable_task`, `tea_create_watch_signal`, `tea_read_memory`, `tea_write_deliverable`, `tea_search_tools` | Exclude all write actions from V3 read-only testing; review read functions only after target queue and deliverable contracts are verified |

The audit found 43 visible functions or procedures in the legacy personal schema. The table above lists the functions relevant to this V3 design, not a claim that every legacy function is active in production today. A fresh read-only function inventory is required before the final retain, rebuild or retire decision.

### V3 function decision register

For every function connected to an agent, record:

- exact function name;
- business capability;
- input parameters and null behavior;
- output grain, columns and row limit;
- current tables or views read;
- freshness and snapshot behavior;
- deterministic or model-backed behavior;
- read-only or side-effecting behavior;
- consumers and agent attachment;
- verified questions that need it;
- decision: retain, rebuild, replace with view, retire or not in scope.

The default rule is: use a curated view and reviewed SQL example first. Add a UC function only when the verified capability still cannot be answered safely and consistently.

### How functions fit into the three-way test

Flexible table and view questions will be tested first without custom functions. Function-backed capabilities will be a separate test group.

If a function is included in the formal three-way comparison, all three arms must receive an equivalent function signature, parameter behavior, return grain and business logic. Only the underlying source may change. One arm cannot use a precomputed function while another must derive the answer from several tables.

All benchmark functions must be read-only. Task creation, updates, notifications, writes and model-calling functions are excluded from the controlled data benchmark.

## Agent design

The agents should be separated by business domain, not blindly by table.

```text
                         Central Sales AI agent
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
          v                       v                       v
    CSM specialist         Finance specialist       Case specialist
          |                       |                       |
 Booking, allocation,       AR customer view        Case and issue views
 MQC and swap views         and approved lookups    and approved lookups
          |
          +------------------------------------------------+
                                                           |
                                                           v
                                                  Workspace specialist
                                                 Roster and deliverables
```

Recommended specialist roles:

1. CSM specialist for booking, allocation, commitment, MQC and swap-screening questions.
2. Finance specialist for AR snapshot and aging questions.
3. Case specialist for parent cases, child issues and lifecycle questions.
4. Workspace specialist for roster assignment and deliverable questions.

The central agent only identifies the business intent, sends the question to the correct specialist and combines returned answers when a verified cross-domain question requires it. It should not rebuild business formulas in its prompt.

Each specialist receives only its domain views and approved read-only functions. It also receives a short contract describing grain, valid filters, non-additive measures, exact names, date meaning, supported questions and unsupported actions.

### How Genie should answer

```text
User asks a question
        |
        v
Central agent identifies the domain
        |
        v
Specialist checks whether the request is supported
        |
        +-----------------------------+
        |                             |
        v                             v
Query a curated view          Call an approved UC function
for flexible analysis         for a fixed narrow capability
        |                             |
        +--------------+--------------+
                       v
           Validate grain and result shape
                       |
                       v
              Return a clear answer
```

If a question needs unsupported history, an unapproved threshold, a write action or a true swap probability that the data cannot prove, the specialist should explain that limitation rather than manufacture an answer.

## Three-way controlled benchmark

| Test arm | What its agents can read | What it proves |
|---|---|---|
| A: Current Gold | Frozen, source-shaped copies or time-pinned references to the six current Gold tables | The current data-access baseline |
| B: Normalized direct | Facts, dimensions and bridges | Whether explicit grains improve correctness when the agent must still choose joins |
| C: Curated | Small domain views over the normalized model | Whether a prepared semantic contract improves agent accuracy, consistency and SQL simplicity |

Use the same specialist domains in all three arms. Test the specialists directly first. Only after those tests pass should three matched central agents be tested for routing and cross-domain questions.

The live production agent may be asked the same read-only questions as an observational smoke test. It is not part of the causal score unless its data snapshot, instructions, tools, model and settings can be matched. Otherwise the report will clearly label it as a separate observation.

### Controls

- Same frozen source population.
- Same exact question wording.
- Same independently verified expected result.
- Same warehouse, time zone, row limit and instruction contract.
- Same managed model configuration where Databricks exposes it.
- New conversation for every independent repetition.
- Randomized or interleaved A, B and C run order.
- No silent retries.
- Cold and warm query observations recorded separately.
- Direct SQL execution measured separately from end-to-end agent time.

If Databricks does not expose the base model, the result will be described as a comparison of complete managed setups, not proof that the data architecture alone caused the difference.

### Questions and ground truth

The existing 41-question bank is the starting inventory. A question becomes scoreable only after it has:

- a verified business or specification source;
- a declared business process and grain;
- canonical read-only SQL;
- an exact expected column list and ordering;
- tie-break rules;
- numeric precision and null rules;
- a result hash from the frozen sample;
- independent technical review;
- a status of `TECHNICALLY_VERIFIED`, `BUSINESS_APPROVED`, `DRAFT` or `UNSUPPORTED`.

An agent answer cannot become ground truth automatically. DRAFT questions can still be used for discovery, but they will not be mixed into the accuracy score.

The verified test set must cover all Gold domains and known edge cases, including repeated booking values, invalid denominators, cumulative AR buckets, multiple roster assignments, duplicate case natural keys, suppressed or deferred issues, deliverable version chains, invalid payloads, cross-domain routing and unsupported write or prediction requests.

### Metrics

| Area | Measures |
|---|---|
| Data preservation | Column coverage, source-record coverage, reconstruction mismatches, row and grain parity, type/null variance, orphan and collision counts |
| Answer quality | Correct rows, values, columns and ordering; formula and grain correctness; correct refusal of unsupported requests |
| Reliability | Success, error, timeout and retry rates; result consistency across repetitions |
| SQL quality | Referenced objects, joins, join depth, CTEs, subqueries, SQL length and `SELECT *` usage |
| Performance | SQL execution time, warehouse wait, first result, end-to-end latency, rows/files/bytes scanned where available |
| Routing | Correct specialist, allowed-source use, UC-function selection and cross-domain handoff |
| Maintainability | Number of exposed objects, duplicated formulas, documented contracts and test coverage |

Three repetitions are useful for a pilot consistency check. They are not enough for a strong p95 latency claim. At least 20 comparable observations are needed before reporting a meaningful p95, together with an agreed service target or equivalence margin.

## Notebook plan

Use five focused notebooks rather than one long notebook that is difficult to debug.

| Notebook | Purpose |
|---|---|
| `00_v3_scope_freeze_and_sample` | Read current Gold inventory, choose the month, pin versions and create the personal sample manifest |
| `01_v3_normalized_model_build` | Build facts, dimensions, bridges, column map, compatibility views and curated views in the personal schema |
| `02_v3_no_data_loss_validation` | Run reconstruction, grain, key, type, null, hash, measure and relationship checks; stop on a blocking failure |
| `03_v3_ground_truth_and_agent_benchmark` | Register verified questions, run the controlled A/B/C specialist and central-agent tests and retain raw evidence |
| `04_v3_results_and_recommendation` | Produce the coverage matrix, scorecards, charts, limitations and final evidence-based recommendation |

All imports and configuration belong at the top of each notebook. Every write uses a versioned V3 run ID, targets the personal schema and is idempotent. The publish manifest is written last, only after its required validations pass.

Supporting personal control tables:

- `v3_source_manifest`
- `v3_sample_manifest`
- `v3_column_map`
- `v3_grain_contract`
- `v3_row_lineage`
- `v3_function_register`
- `v3_validation_results`
- `v3_ground_truth_registry`
- `v3_benchmark_runs`
- `v3_benchmark_summary`

These control tables make the result reproducible. They are not new production objects.

## Build and approval gates

### Gate 1: Scope is complete

- Current Gold tables and schemas are captured from Databricks.
- Every source column is registered.
- The active producers and relevant UC functions are inventoried.
- The chosen month and table-specific selection rules are documented.

### Gate 2: The normalized sample is lossless

- All six compatibility views reproduce their frozen source samples.
- Grain, key, relationship, measure, null, type and hash checks pass.
- Every exception is documented.

### Gate 3: Ground truth is ready

- Questions cover every Gold domain.
- Only technically verified questions enter the score.
- Unsupported capabilities have an explicit refusal expectation.

### Gate 4: Specialists pass

- A, B and C specialist agents complete the same controlled test.
- Source isolation, correctness and reliability are acceptable.

### Gate 5: Central routing passes

- The three matched central agents route the same cross-domain questions.
- Routing failures are separated from data-query failures.

### Gate 6: Recommendation is evidence-based

- Accuracy, reliability, complexity and performance are reported together.
- Data preservation is proven for the frozen sample.
- Limitations are stated clearly.
- Production remains unchanged until a separate owner review and migration decision.

## What V3 can and cannot claim

V3 can show which of the three personal data-access patterns works best for a frozen, controlled sample and a verified set of questions.

V3 cannot honestly claim:

- normalization is faster simply because there are more tables;
- a narrow view replaces every Gold capability;
- one month validates historical thresholds;
- current snapshots provide full event history;
- three repetitions establish a production p95 latency;
- the production agent is directly comparable when its model or configuration is hidden;
- the new design is ready to replace production before all source columns and compatibility gates pass.

## Expected decision after V3

The likely long-term pattern is:

```text
Normalized facts and dimensions
              +
Grain-safe reusable domain marts
              +
Small stable views for Genie
              +
Only the UC functions that verified testing proves are useful
```

However, V3 will not assume this pattern wins. The final decision will follow the evidence:

- Keep the current Gold access if it is equally accurate, reliable and easier to operate.
- Use normalized facts and dimensions directly if the agents handle the joins correctly and performance remains acceptable.
- Prefer curated views if they improve correctness and consistency without unacceptable latency or maintenance cost.
- Use a hybrid if different domains have different winners.

## Immediate next step

Create and run only `00_v3_scope_freeze_and_sample` first. It must perform a read-only current inventory, propose the most recent complete month and show the exact tables, versions, schemas, date coverage, row counts and function register before creating any normalized objects.

Stop after that report for review. Do not build facts, dimensions, views, functions or agents until the live scope and sample rules are confirmed.

## Evidence basis and limits

This plan was prepared from the saved table dictionaries, producer-notebook captures, Gold/Silver lineage audit, Story 4950 evidence, CSM Genie audit, V1/V2 benchmark results and the current 41-question bank in this workspace.

It distinguishes three levels of confidence:

- **Verified from saved evidence:** the six documented Sales AI Gold tables, latest captured schemas, known source relationships and observed legacy function behavior.
- **Proposed for V3:** target fact, dimension, bridge, view and agent names.
- **Requires live read-only verification:** current table inventory, active producer versions, exact physical grains, key uniqueness, current UC attachments, date coverage and snapshot synchronization.

That separation is intentional. The design is complete enough to start V3 discovery, but it does not present a dated screenshot or an untested candidate key as current production truth.
