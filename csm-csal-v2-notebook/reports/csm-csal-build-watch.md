# CSM / CSAL V2 progress

Last updated: 10 September 2026

## Overall progress

`[████████████████████] 100%` for the agreed seven-question booking-scope POC

The personal data model, two agent paths, controlled benchmark and manager-ready result are complete. Production was not changed.

| Part | Status |
|---|---|
| Personal facts, dimensions and booking view | Complete |
| Grain, key, row-count and measure validation | Complete; all saved checks passed |
| Comparable wide and curated agent paths | Complete |
| C01 to C07 reference calculations | Technically cross-checked; business thresholds not signed off |
| Controlled A/B execution | Complete; 42 of 42 responses stored |
| Scoring and failure review | Complete |
| Final report and chart | Complete |

## Result in one paragraph

The curated booking view returned 13 proven-correct answers out of 21 planned runs, compared with 12 for the wide baseline. Among the 18 evaluable table answers per path, accuracy was 72.2% versus 66.7%. Both paths had the same consistency score, and median response time was effectively tied at about 40 seconds. This is a small positive signal for the curated view, not proof that production should be rebuilt.

## Decision

Keep the production Gold table unchanged. Keep the personal curated booking view as a pilot. Tighten the output contract for the three weak question patterns, capture structured SQL evidence, then rerun the same test as a new version.

The 41-question bank, hard-scenario bank, threshold calibration, historical enrichment and swap scoring are later phases. They are not part of this completed POC.

- [Full controlled result](csm-csal-v2-controlled-benchmark-results-2026-09-10.md)
- [Manager story](csm-csal-v2-manager-story.md)
- [Architecture](../OBSIDIAN_PRODUCTION_AND_V2.md)
