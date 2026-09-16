# CSM CSAL V3 Seven Evidence Screenshot Guide

## What this guide is for

Use this guide to place screenshots into the seven-evidence report without mixing them with the older ten-metric report. The copy-ready report is [CSM CSAL V3 Seven Strong Evidence Cases](csm-csal-v3-seven-evidence-report.md).

Keep all corporate screenshots inside the Windows VM. Do not upload screenshots or customer-level data to Git. Git contains only this guide, the report text and the approved code copies.

## Files you need

- `reports/csm-csal-v3-seven-evidence-report.md` is the complete copy-ready report text with all headings and screenshot placeholders.
- `reports/csm-csal-v3-seven-evidence-screenshot-guide.md` is this placement and verification guide.
- The Word report stays inside the Windows VM. Copy the report text into that file and replace each placeholder with the matching VM screenshot.
- The detailed Databricks notebook is linked at the end of the report. Open it only inside the Windows VM.

## Folder and file names

Inside the Windows VM, create this folder:

`Desktop\temp analysis\csm-csal-v3-seven-evidence`

Use these names for every case:

- `E01-A-agent.png` for the production main-agent question and answer
- `E01-B-sql-code.png` for the Databricks SQL code
- `E01-C-sql-result.png` for the Databricks result

Replace `E01` with `E02`, `E05`, `E07`, `E08`, `E09` or `E10`. If one image cannot show the full content clearly, use `A1`, `A2`, `B1`, `B2`, `C1` and `C2` in reading order.

## What each screenshot must show

### A Production main-agent evidence

Capture the exact business question and the complete production main-agent answer in the same fresh conversation. The image must make the question, result, agent identity and conversation context readable. If the response is longer than one screen, use two numbered images rather than cutting off text.

### B Databricks SQL code

Capture the read-only SQL used for that exact case. The visible code must show the reporting month, source table, filters, grouping and calculation. Include the pinned version or run reference when it is available. Do not use an image from another metric because the SQL looks similar.

### C Databricks SQL result

Capture the output produced by the code in screenshot B. Keep the important totals, checks, unresolved count and status readable. The code and result must come from the same run.

## Seven-case placement checklist

### E01 Filtered booked TEU

Place the images at the three E01 placeholders in the report.

- A must show the selected customer and agreement question for `2026WK31`, service `PVCS` and TCR `HKG`, with the agent answer of `432 TEU`.
- B must show the SQL that compares the source result, the count-once result and the repeated Gold result for the same filters.
- C must show `144 TEU` from the source, `144 TEU` counted once, `432 TEU` across repeated Gold rows and `0` unresolved records.
- Outcome supported by these images: confirmed grain failure within the captured run.

### E02 Portfolio reviewed commitment

Place the images at the three E02 placeholders.

- A must show the August 2026 reviewed commitment question and the agent answer of `48,389 TEU`.
- B must show the commitment comparison SQL for August 2026.
- C must show source `48,389 TEU`, count-once `48,389 TEU`, repeated Gold `115,396 TEU` and `0` unresolved records.
- Outcome supported by these images: pass.

### E05 Portfolio cancellation percentage

Place the images at the three E05 placeholders.

- A must show the August 2026 cancellation-percentage question and the agent values `18,202` cancelled TEU, `103,364` booked TEU and `17.609613 percent`.
- B must show the SQL that calculates the native booking percentage, the Gold count-once percentage and the repeated Gold percentage.
- C must show `17.033035 percent`, `17.033388 percent`, `17.609613 percent` and `1` unresolved record.
- Outcome supported by these images: strong grain-risk indication, not a confirmed failure.

### E07 TCR detail and parent commitment

Place the images at the three E07 placeholders. Use `E07-A1` and `E07-A2` if the complete agent answer needs two images.

- A must show the selected customer and agreement question for `2026WK32`, service `ECX1`, plus the agent answers of `112 TEU` for ECN and `59 TEU` for the parent reviewed commitment.
- B must show both the TCR-detail comparison and the parent-commitment comparison.
- C must show ECN source and count-once `56 TEU`, ECN repeated `112 TEU`, parent source and count-once `59 TEU`, and parent repeated `708 TEU`.
- Outcome supported by these images: mixed result. The ECN detail is a grain-related mismatch and the parent commitment passes.

### E08 Category and volume without CSAL structure

Place the images at the three E08 placeholders.

- A must show the structural question and the agent answers of `1,235` multi-category combinations and `1,163` conflicting flag combinations.
- B must show the SQL that groups booking combinations and counts category and flag differences.
- C must show `12,403` booking combinations, `283` multi-category combinations and `195` conflicting flags.
- Outcome supported by these images: does not reconcile. The current evidence does not isolate grain as the cause.

### E09 Unique active IB CSAL cases

Place the images at the three E09 placeholders.

- A must show the unique active IB CSAL case question and the agent answer of `390` cases.
- B must show the SQL that counts each active case once and compares it with repeated Gold rows.
- C must show `444` unique active cases, `12,452` repeated Gold rows and `3` unresolved comparisons.
- Outcome supported by these images: unresolved. It is not a confirmed grain failure.

### E10 Reviewed allocation TEU control

Place the images at the three E10 placeholders. If the question and answer are in separate captures, use `E10-A1` and `E10-A2`.

- A must show the August 2026 reviewed allocation question and the agent answer of `48,389 TEU`.
- B must show the SQL comparing the source, allocation-grain and Gold calculations.
- C must show `48,389 TEU` for every tested path and `0` unresolved records.
- Outcome supported by these images: pass and control case.

## Current screenshot review

Do not insert the current screenshot files without checking them against this list.

- The current E01 agent image is obstructed by a context menu. Retake it.
- The current E02, E05, E08 and E09 agent images show the answer but not the full question. Retake them or capture the question and answer as numbered images.
- The current E07 answer is split across two response fragments. Keep both in order or retake one complete view.
- E10 already has separate question and answer images. Insert them as `E10-A1` and `E10-A2` if both are readable.
- No aligned original B or C screenshot set is currently available for these seven cases. Capture each SQL code and result from the matching Databricks run.

Never use these files in the seven-evidence report:

- `E09_sql_result_vm_view.png` because it shows an older cancellation-percentage case, not current E09.
- `temp_sql_saved_01.png` because it shows an older missing-identity case, not current E10.
- `rendered/E##_evidence_composite.png` because these are recreated composites, not original Databricks captures.
- Any `*-v86` screenshot because those files use E-numbers from a different report.

## Insert each image in Word

1. Find the matching placeholder, such as `[VM SCREENSHOT E01-A: Production main-agent question and answer]`.
2. Delete only that placeholder line.
3. Select **Insert**, then **Pictures**, then **This Device**.
4. Choose the matching file from `Desktop\temp analysis\csm-csal-v3-seven-evidence`.
5. Set **Wrap Text** to **In Line with Text**.
6. Keep the original aspect ratio and make the text readable without stretching the image.
7. Put the caption directly below the image. Example: `Screenshot E01-A. Production main-agent question and answer.`
8. Keep the explanation that follows the screenshot. Do not replace the report conclusion with Copilot's interpretation.
9. Save the same Word file after each evidence case.

## Copilot check prompt

Paste this prompt into Copilot with one screenshot at a time:

> Check this screenshot only against case E01 in the CSM CSAL V3 Seven Evidence Screenshot Guide. Confirm whether it shows the required question or SQL, the expected filters and the expected values. Do not infer any missing information. Reply with PASS or RETAKE, followed by the exact reason. Also confirm the correct file name and placeholder, such as E01-A, E01-B or E01-C.

Replace `E01` with the case being checked.

## Final check before sharing the report

- All seven cases have A, B and C evidence, or a clearly labelled missing-evidence placeholder.
- Every B and C pair comes from the same Databricks run.
- Every question and answer is readable.
- E01, E02, E05, E07, E08, E09 and E10 use the meanings in this guide, not the older ten-metric numbering.
- No customer-level records, screenshots or corporate data were added to Git.
- The conclusions remain unchanged unless new evidence genuinely changes them.
