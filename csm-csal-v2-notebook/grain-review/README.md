# CSM/CSAL grain review

This replaces the earlier unconditional `MAX()` comparisons and the requirement to collect ten failures. It tests proposed groupings and records what the data supports. No preferred total, reduction percentage or number of agent failures is configured.

## Start at the office

1. Open [COPY_CELLS.md](COPY_CELLS.md). It contains the complete code in eight numbered Python cells.
2. Use a separate personal analysis notebook named `CSM_CSAL_GRAIN_REVIEW`. Keep the earlier report notebook as historical evidence.
3. Paste one block per cell and run cells 1–8 in order. No package installation is needed in Databricks. The notebook uses standard Python, PySpark and read-only SQL.
4. Cell 1 defaults to August 2026 and selects the latest Delta version once. For historical v86 work, set `SOURCE_VERSION = 86` before running. It never silently falls back to another version.
5. After the first run, use the printed version number explicitly for reproducibility. Rerunning with `None` may select a newer version.
6. Stop at the first failed cell. Do not continue with old outputs. No cell contacts an agent, changes a table, creates a view, writes files or changes permissions.

You can also import [CSM_CSAL_GRAIN_REVIEW.py](CSM_CSAL_GRAIN_REVIEW.py) as a Databricks source notebook. That file and the eight blocks in the copy guide are identical.

## What each cell provides

| Cell | Purpose | What to capture |
|---|---|---|
| 1 | Pin the table version, select the month, record schema hash, row count and source column count | Run metadata and version output |
| 2 | Profile every column for nulls, blanks and invalid numeric values; inspect visible constraint declarations and potential name-cleaning collisions | Column-quality output and constraint status |
| 3 | Define the numerical comparison with checks before combining values | Nothing needs to be captured yet |
| 4 | Declare the candidate grouping columns and original field-mapping hypotheses | Candidate-scope output |
| 5 | Test every scalar column against all five candidate scopes; show newly added, unmapped or unsupported fields | Complete column coverage and relevant conflict rows |
| 6 | Examine all 25 listed amounts/counts across allocation, booking, commitment, monthly and agreement context | Candidate totals, blockers and excluded-row counts |
| 7 | Print exact SQL for one metric, display its result and test added grouping columns | SQL code and result for each evidence case |
| 8 | Record completion metadata and whether the source advanced during the run | End-of-run source-version check |

Cell 5 makes several aggregate scans. It covers the source's actual columns, whether there are 79, 82 or another number. Coverage does not mean every business definition is approved. Complex types are reported as requiring review rather than silently converted to strings. Grouping fields are marked as such: a key column is constant within its own group by construction.

## How the numerical check works

For each proposed group, the SQL counts physical rows, distinct non-null metric values, null metric rows, non-finite values and missing grouping attributes. `COUNT(DISTINCT)` normally ignores nulls, so a separate null state is included in the consistency test. NULL and zero stay different. NULL and a populated metric in the same group are a conflict.

`MIN()` retrieves a sole value only when exactly one non-null value is present and all completeness checks pass. It does not choose a minimum instead of a maximum to resolve disagreements. Replacing MAX with MIN, FIRST, SUM DISTINCT or dropDuplicates alone would not fix the evidence problem.

Original numeric types are used for calculations. No whole-number rounding or integer coercion is added. The multi-metric display converts final results to strings only after each native-type calculation finishes, to avoid an implicit precision change when combining different numeric types.

Every physical row remains accounted for. Groups with missing keys, missing metric values, conflicts or invalid numbers are excluded from the explicitly named `eligible_candidate_subtotal`. Their row counts are shown. If any such group exists, the full `candidate_grain_total` and full comparison difference are NULL. Never compare a partial subtotal with an agent's entire-portfolio answer.

An all-null sum remains NULL. An empty sample stops the notebook. NaN and positive or negative infinity block the numeric comparison. Zero and negative amounts remain visible; smaller values are not assumed to be better values. Signed values can also cancel differences even when repetition exists.

## Reading the statuses

| Status | Meaning | Reporting action |
|---|---|---|
| `CONSISTENT_CANDIDATE_NOT_BUSINESS_VALIDATED` | This sample has one populated metric value per proposed group and complete grouping attributes | Describe a candidate calculation; still verify identity, grain and additivity |
| `BLOCKED_CONFLICT_OR_INVALID_VALUE` | Different values, null-versus-value conflicts or invalid numbers prevent a safe collapse | Show the issue; do not select MAX/MIN to make it disappear |
| `BLOCKED_NON_FINITE_AGGREGATE` | A total overflowed to infinity or became NaN even though the inputs may be finite | Do not use the aggregate as evidence; investigate the numeric range |
| `BLOCKED_INCOMPLETE_KEYS_OR_VALUES` | Missing grouping attributes or all-null metrics prevent a complete comparison | Keep the missing population visible and resolve its meaning |
| `EMPTY_SCOPE` | No source rows | No conclusion is possible |
| `CONSTANT_IN_SAMPLE_ONLY` | One field is constant at the tested scope in this sample | An observed dependency, not a declared key or approved formula |
| `CONFLICT` | One field varies within the proposed scope | The proposed grouping cannot preserve that field as a single value |
| `NEEDS_MAPPING` / `UNSUPPORTED_TYPE_NEEDS_REVIEW` | The schema contains a field the current mapping or scalar check cannot interpret | Retain it explicitly in the coverage inventory |

Missing names or agreement values are not deleted or automatically combined into a single business entity. A future unknown-member strategy needs its own validated handling rule; it cannot establish that two missing identities are the same entity.

## Identity, month and primary keys

Customer names remain unchanged. Uppercase/trim is used only to count possible cleaning collisions; it never merges customers. Equal names can still represent different customers, and different spellings can represent the same customer. Validate an authoritative ID or the documented source-system identity rule before certifying a business grain. Hashing a name does not solve this problem.

Month is included in every candidate, including booking. In a query already restricted to one exact month, adding month does not change the grouping. It prevents cross-month collapse if this check is later extended to multiple months; it does not automatically validate the business calendar or a weekly-to-month relationship. The source month label is the current filter, not a guarantee of event-date semantics.

The notebook attempts to read currently visible PK/FK metadata. Empty or unavailable metadata is not asserted to prove that no key exists, and current metadata does not prove historical v86 constraints. A declaration is also different from observed uniqueness. Databricks PK/FK constraints are informational; key quality must be tested separately. [Databricks constraints](https://docs.databricks.com/aws/en/tables/constraints)

Adding grouping columns often removes conflicts simply because groups become smaller. Cell 7 shows this sensitivity without choosing whichever grouping produces the smallest total or the most favourable outcome. A unique row count by itself does not identify the correct business event.

## All business areas are visible, but need different validation

- Amounts and counts: the notebook compares 25 candidate aggregations and retains zero differences. Even a count can repeat across broader scopes; confirm additivity across the requested report dimensions.
- Percentages: verify the approved numerator, denominator and scale. Neither summing percentages nor taking an unweighted average is automatically valid. No denominator is invented here.
- Existing averages: establish the weighting basis and population before computing an overall average.
- Flags, issue scores and cutoff values: inspect field consistency and business rules. Stable values do not prove the threshold, date basis or interpretation.
- CRM, vessel/voyage and location text: preserve the supplied values. A comma-separated field does not establish a unique event ID or recover discarded event history.
- MQC/agreement context: verify the agreement identity and as-of semantics before adding contract-level measures across customers or periods.
- New schema columns: shown as unmapped until their role is established.

## Ten existing evidence topics

These are the existing report topics. They are not a target of ten failures. Keep every outcome and retain prior captures as historical observations.

| Topic | `EVIDENCE_METRIC` in cell 7 | Neutral production question |
|---|---|---|
| E01 | `monthly_booked_teu` | For August 2026, what is the total monthly booked TEU? |
| E02 | `monthly_cancelled_teu` | For August 2026, what is the total monthly cancelled TEU? |
| E03 | `monthly_rejected_teu` | For August 2026, what is the total monthly rejected TEU? |
| E04 | `monthly_confirmed_teu` | For August 2026, what is the total monthly confirmed TEU? |
| E05 | `booked_teu` | For August 2026, what is the total booked TEU? |
| E06 | `confirmed_teu` | For August 2026, what is the total confirmed TEU? |
| E07 | `cancelled_teu` | For August 2026, what is the total cancelled TEU? |
| E08 | `rejected_teu` | For August 2026, what is the total rejected TEU? |
| E09 | `no_show_teu` | For August 2026, what is the total no-show TEU? |
| E10 | `terminated_teu` | For August 2026, what is the total terminated TEU? |

The amount checks also cover the other 15 mapped amounts/counts, including reviewed allocation, commitment, swap fields and MQC. Those outputs belong in the audit whether they support the earlier hypothesis or not. Rates, flags and text have a separate consistency review in cell 5 and remain pending semantic verification.

## Screenshots and the existing Word report

Keep `Desktop\temp analysis\csm csal v3 grain analysis report.docx` as the report. For each topic:

1. Run cells 1–6 and note the pinned source version. For cell 7, set the metric from the table above and run the cell.
2. Copy the printed SQL into a personal SQL Editor query. It already includes the source version and month; do not remove them. Run only that read-only SELECT.
3. Capture the SQL code and its result. If they cannot both fit legibly, take two screenshots named `E01-vNN-code.png` and `E01-vNN-output.png`, replacing E01 and NN with the actual topic and version. Include the status, exclusions and null counts in the output capture. Use extra output images rather than hiding important columns.
4. If a repeated-group example is needed, set `SHOW_GROUP_DETAILS = True` in cell 7. This displays at most ten deterministic groups, their row counts and observed value ranges. These examples are for inspection and do not form a representative accuracy sample. Keep source-level details in the office environment.
5. Pair the SQL images with the production main agent's actual question and response, conversation/time reference, and generated SQL or UC-function/tool trace if available. Fresh chats use the fixed question wording. Do not keep asking until a desired error appears.
6. Record the actual source/filters used by the agent. A date near the SQL query time is not enough to establish the same data version. If the trace does not identify the version or input source, mark snapshot alignment unverified. Do not reuse old v86 answers with a current-source query.
7. In the existing Word section, use this sequence: question; production response; SQL code; SQL output; evidence-specific explanation. Place images inline, keep their aspect ratio and check readability at normal zoom.
8. Use a genuine Databricks result image to replace the manually typed summary table. Its captions must say candidate calculation and show blockers where present.

Do not present the 25 separate result scans as a database performance benchmark. An agent latency claim needs a separate controlled test with comparable settings, scope and workload.

## How to write each explanation without overstating it

For a consistent candidate:

> The SQL found [N] physical rows and [G] proposed groups. The metric was constant within those groups, with [counts] missing values or keys. The direct source sum was [R], and the candidate calculation was [C]. This supports the observed grouping in this sample. Its business meaning and additivity still require verification against the deployed source logic.

For an incomplete or conflicting candidate:

> The candidate check found [N] conflicting groups and [M] rows with missing keys or values. It therefore withheld a complete candidate total. The displayed subtotal covers only the eligible groups and cannot establish whether the production answer is right or wrong for the full portfolio.

For an agent result matching the direct sum:

> The agent returned [A], which matches the direct source sum. This numerical match is an observation. The agent's actual SQL or tool trace, source alignment and a verified business reference are required before attributing the result to repeated-value aggregation.

Only call something a demonstrated grain-related error when the approved business grain and formula establish the reference result, relevant identity/null handling is resolved, the agent uses comparable data and filters, and its trace shows the unsuitable aggregation. If trace access is unavailable, state that the mechanism is unverified. A wrong answer can be established against an independent reference without proving its internal cause.

Keep correct, incorrect, unresolved, refused and failed-execution outcomes in the complete test log. The visible report can illustrate selected cases, but label that selection and do not turn it into an overall accuracy rate. No percentage or latency advantage is claimed by this notebook.

## What changed from the earlier guidance

- The label `correct_grain_total` was premature. It is replaced with a guarded `candidate_grain_total`.
- The requirement that outputs match ten historical totals is removed. New results are recorded as observed.
- Matching the raw sum alone no longer counts as proof of agent failure or its cause.
- Missing keys and null metrics are visible; a whole-portfolio result is withheld until the proposed grouping is complete.
- The historical claim that all 79 fields were business-validated is narrowed to the checks actually performed. Round-trip preservation tests information retention, not the correctness of every formula or entity identity.
- The latest team message reports a specific swap-demand fix. Its scope and post-rerun outcome still require verification. A non-zero comparison by itself neither disproves that fix nor proves the production design is wrong.

## Validation of this code

Eight cells pass Python syntax checks. The SQL helper passed 25 synthetic tests covering conflicts, nulls, missing keys, independent entities with equal amounts, precision, signed values, NaN/infinity, overflow, empty inputs and added-key sensitivity. Exact generated SQL is parsed as Databricks SQL and translated for local execution with DuckDB. This checks logic without using corporate data; it is not a Databricks runtime or production-data validation. The PySpark profiling cells still require execution in your workspace.

The notebook never guarantees 100% business correctness. Its purpose is to make assumptions, observations and unresolved evidence explicit so the eventual conclusion can be defended.

## Reference principles

Grain represents what one row measures and should be established before choosing facts or dimensions. Sample uniqueness or lower totals cannot establish that meaning alone. [Kimball Group: grain](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/grain/)

The null-aware tests follow documented `COUNT(DISTINCT)` behaviour. [Databricks COUNT](https://docs.databricks.com/aws/en/sql/language-manual/functions/count)

The source version is pinned because a live table can change between checks. Historical access depends on retained data files as well as log history; the notebook does not substitute current data if time travel fails. [Databricks table history](https://docs.databricks.com/aws/en/tables/history)
