# Ten-Evidence SQL Validation Record

## Scope

This record covers the local review of the read-only ten-case CSM/CSAL evidence package. It does not certify live data values, the currently deployed producer revision or a production-agent error.

The package creates no table, view or function. It makes no change under `madabra`, `usr.jayarsr` or any other schema. If a later V3 build is separately approved, its personal objects must be created only under `usr.jayarsr` after confirming the signed-in identity and target schema.

## Five review passes

1. **Tables, columns and data types**

   The ten selected metrics, required grouping fields and retained upstream fields were checked against the saved Gold schema and producer code. Numeric inputs use guarded conversion, and null, invalid, fractional and out-of-range populations remain visible.

2. **Producer formula and lineage**

   The producer replay was compared with the retained producer logic for the ten TEU measures. It is labelled as a retained-code replay, not as proof of the deployed producer. The curated `csal_teu_performance` table is treated as an intermediate source rather than independent raw truth.

3. **Grouping, joins and row repetition**

   The review checks candidate-group consistency, missing and blank keys, final Gold row repetition, producer monthly fan-out, unmatched allocation rows, cross-month merging and sales-attribution differences. A numeric subtotal is not accepted as a complete result when any group is blocked.

4. **Month, filters, status and versions**

   Gold and upstream reads require explicit versions and the same reporting month. The output reports upstream run dates, null run dates and non-report-month leakage. The final conclusion stays unresolved until both versions are tied to the same producer run and the raw-source filters and status rules are verified.

5. **Databricks safety and conclusion rules**

   The SQL was checked for Databricks syntax, aggregate legality, CTE dependencies and aligned union projections. It contains no write, DDL or configuration statement. Agent-error attribution requires one selected case, a parsed agent answer, the executed agent trace, aligned scope, confirmed unsafe aggregation, an independent raw reference and approved identity and metric rules.

## Validation results

- All six SQL blocks in the compact pack parsed as Databricks SQL.
- All ten generated copy cells parsed as Databricks SQL.
- All 55 existing grain-review regression checks passed.
- The copy guide regenerates from the compact source and contains the complete parameter set in every case.
- Synthetic execution covered a booking repetition case, a correct agent answer, missing evidence gates, invalid numeric input, cross-month leakage, an empty scope and monthly producer fan-out.
- The read-only safety scan found no `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `ALTER` or configuration statement.
- The final independent Astra audit passed.
- A separate SQL logic and safety audit passed.
- A separate copy-guide audit passed.

## Live checks still required

### Parameter setup correction

The reported `UNBOUND_SQL_PARAMETER` error exposed a missing execution setup step. Local SQL parsing did not test notebook widget binding. The copy guide now includes a missing-only widget setup cell, SQL warehouse UI instructions and an explicit `spark.sql(..., args=...)` route.

Four focused local tests pass for complete marker coverage, preserving existing inputs during repeated setup, refreshing the Python argument mapping and rejecting missing or invalid snapshot selections. These tests use a widget stub and do not claim a live Databricks execution. The evidence SQL calculations are unchanged.

### Remaining evidence

The following are evidence gates, not local code defects:

1. Confirm that the selected Gold and upstream Delta versions are retained and belong to the same producer run.
2. Resolve the approved raw movement, shipment-status and TCR-map objects from the executed producer revision.
3. Rebuild each reference total from those raw sources using the same reporting scope.
4. Capture the production main agent's answer and its executed SQL, UC function or tool trace for each case.
5. Confirm the candidate identity and metric rules with the responsible business owner.
6. Rerun one case at a time and capture the SQL, complete result and version metadata.

Until those checks pass, the package may report a repetition pattern or an unresolved producer limitation, but it must not report a confirmed production-agent error.

## Runtime note

The package uses named parameters in `VERSION AS OF`. If an older Databricks runtime rejects that form, replace only the version marker with the already captured numeric Delta version in the private office copy. Do not substitute an unpinned current-table read.
