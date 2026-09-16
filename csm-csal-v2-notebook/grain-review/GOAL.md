# Current Goal

## Objective

Create one copy-ready Markdown notebook containing ten read-only SQL evidence cases that test whether the production main agent returned an incorrect CSM/CSAL total because the same business value was repeated across multiple Gold-table rows.

## Ownership boundary

This evidence work is read-only and must not create any table or view. `madabra` is not the project owner. If a later V3 build is explicitly approved, personal objects may be written only under `usr.jayarsr`, after confirming the signed-in identity and target schema.

## What each evidence case must prove

Each case must show all of the following on the same reporting month and aligned data versions:

1. The value returned by the production main agent.
2. The calculation behind the visible Gold-table total.
3. The rows where the same business value is repeated.
4. The value rebuilt from the earliest reliable source available in the saved producer lineage.
5. The value after each valid business record is counted once.
6. Whether the complete difference is explained by row repetition.

A case is labelled as a grain-related agent error only when the source result and count-once result agree, the agent result matches the repeated Gold-table calculation, and no material filter, version, status, null, or join difference remains unresolved.

## Ten measures in scope

- Monthly booked TEU
- Monthly cancelled TEU
- Monthly rejected TEU
- Monthly confirmed TEU
- Booking-grain booked TEU across the selected reporting month
- Booking-grain confirmed TEU across the selected reporting month
- Booking-grain cancelled TEU across the selected reporting month
- Booking-grain rejected TEU across the selected reporting month
- Booking-grain no-show TEU across the selected reporting month
- Booking-grain terminated TEU across the selected reporting month

## Required quality checks

The completed Markdown must pass five separate reviews:

1. Table, column, and data-type accuracy.
2. Producer-formula and lineage accuracy.
3. Join, grouping, and row-repetition accuracy.
4. Month, filter, status, and data-version alignment.
5. Databricks compatibility, read-only safety, and unbiased conclusion rules.

An independent Astra review will challenge the completed logic before delivery. Live Databricks execution remains the final validation because local files cannot confirm current permissions, retained Delta versions, or live source values.

## Current status

- The 79-column Gold schema and retained producer logic have been reviewed.
- The ten-metric read-only SQL pack and copy-ready Markdown have been created.
- The pack now separates final-row repetition, producer monthly fan-out, guarded intermediate totals, independent raw references and agent attribution.
- Local parser and synthetic-data checks have passed. Independent reviews identified edge cases around empty scopes, cross-month leakage, numeric conversion and blank keys; those corrections have been applied.
- A final independent Astra review, a separate SQL logic review and a copy-guide regeneration review all passed. These reviews validate the local package, not the live data result.
- Live Databricks execution, raw-source binding, deployed-producer alignment and production-agent trace capture remain required before any metric can be reported as a confirmed production error.

## Completion rule

The local preparation task is complete only when the copy-ready Markdown is internally reviewed, contains ten executable read-only diagnostic cases, makes no unsupported claim, and clearly identifies what the live Databricks and raw-source runs must confirm. The later live evidence run is a separate completion gate and cannot be replaced by local review.

The later screenshot report and V3 table or agent implementation are outside this immediate task.
