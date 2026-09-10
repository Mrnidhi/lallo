# Sales AI V2 benchmark notebook

Status: C01-C07 controlled personal POC complete on 10 September 2026.

## What completed

- 7 booking-scope questions
- 2 personal main-agent paths
- 3 repetitions per question
- 42 of 42 responses stored and scored
- No production changes

The wide path produced 12 proven-correct answers out of 21 planned runs. The curated booking path produced 13. Across the 18 C01-C06 table-answer runs per path, accuracy was 66.7% versus 72.2%. Both paths were stable for three of four comparable question groups, and no clear latency winner was observed.

## Canonical cells

Files `26` through `53` are the local, one-file-per-cell source for the existing personal Databricks notebook. Imports stay in cell `26`.

- `43` and `44`: create and operate the isolated CSM checkpoint
- `47` and `48`: request cells; do not rerun after completion
- `49`: read saved answers without contacting an agent
- `50`: deterministic offline scorer
- `51`: readable benchmark summary
- `52`: failure reasons without customer-level rows
- `53`: saved SQL-evidence audit

The completed checkpoint already contains all 42 responses. For review, use cells `49` to `53` only. Do not rerun `47` or `48`, do not use Run All, and do not modify the saved checkpoint.

## Decision

Keep production unchanged. Continue the curated booking view as a pilot, tighten the output contract for C01, C03 and C06, capture structured SQL traces, and rerun the same seven questions under a new experiment version.

The wider 41-question and hard-scenario banks are coverage plans, not completed controlled benchmarks.

## Documents

- [Project summary](PROJECT_SUMMARY.md)
- [Question bank](question_bank.md)
- [Production and V2 architecture](OBSIDIAN_PRODUCTION_AND_V2.md)
- [Simplified production and V2 diagram](reports/csm-csal-before-and-current-v2-diagram.md)
- [Full controlled result](reports/csm-csal-v2-controlled-benchmark-results-2026-09-10.md)
