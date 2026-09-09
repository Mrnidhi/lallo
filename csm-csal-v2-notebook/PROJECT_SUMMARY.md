# CSM / CSAL V2: what we are doing and where we stand

Updated: 9 September 2026

## What was our goal?

We want the sales agents to give more accurate, consistent answers, with simpler queries and, if testing supports it, faster responses.

If someone asks, "Which customers have low booking fulfillment?", the agent should find the right records without counting the same booking numbers twice. We are testing this in a personal workspace. Production stays unchanged.

## Why did we start this?

Simple questions were sometimes leading to long SQL, missing columns or incorrect answers. Our frozen CSM baseline has 78 columns, but column count alone does not make a design bad.

We want to find out whether clearer data organization makes the agent's job easier. The before-and-after test will tell us whether the change is worth keeping.

## What have we built?

We created seven dimension tables describing things such as customers and services, and three fact tables separating allocation, booking and commitment numbers. A ready-to-query booking view connects these for the agent. Saved checks passed for relationships, row counts and important totals.

There are now two personal main agents:

- **Before:** uses the existing wide-table structure through a personal copy.
- **After:** uses the cleaner booking view built over our fact and dimension tables.

Both have the same four shared specialists for finance, cases, sales workspace information and CSAL detail. Only their CSM specialist differs. This is not a rebuild of every Gold table or a replacement of production agents.

We also have a 41-question bank, the testing notebook, architecture diagrams and progress notes. The full target is now all 41 questions. The current notebook supports a 12-question first batch; the other 29 still need their test and scoring setup.

## Where are we now?

The main construction is done. The comparison is not.

The expected-answer preparation previously passed its checks. The current manual run is stopping at cell 7; its exact error still needs confirmation. A diagnostic is ready to show the recorded preparation and review statuses. The final report is not ready yet.

There are no verified V2 results yet. The smaller V1 test improved accuracy but was not faster. We cannot extend that finding to the complete V2 setup without testing it.

## What is still pending?

1. Resolve cell 7, review the expected answers and confirm the agent settings. Do not bypass checks.
2. Run one question through both agents. Confirm responses and supporting SQL can be captured and saved.
3. Ask the same 12 questions three times per agent: **72 planned runs** in total, including the first pair. Failed runs must be recorded too.
4. Compare correct answers, consistency, speed, SQL complexity and whether records were counted correctly. Mark missing evidence honestly.
5. Extend the test to the remaining 29 questions. Some need numerical answers, some test an honest explanation of limits, and one needs a two-message conversation. Report all 41, keeping pending tests and guardrail outcomes separate from numerical accuracy.

Databricks manages the underlying models, so we cannot prove they are identical. We will compare the complete setups, not claim the redesign alone caused any difference.

Enrichment, historical threshold changes and swap scoring remain parked. They are not required to finish this first comparison.

## The short version

The alternative structure and agents are built. Now we need to finish the checks, run the comparison and show whether it actually helps.

Next action: follow [the cell 7 review guide](CHECK_CELL_7.md) and share the diagnostic statuses and exact error, not business rows.

[The office Copilot handoff](OFFICE_COPILOT_HANDOFF.md) explains how to continue through the full question bank.
