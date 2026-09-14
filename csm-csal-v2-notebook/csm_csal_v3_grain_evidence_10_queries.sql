-- Superseded: the earlier unconditional MAX() queries and "correct_total" labels
-- assumed the business grain and could hide nulls or conflicting values.
-- Use grain-review/COPY_CELLS.md. Run cells 1-6, then use cell 7 to print
-- the complete version-pinned SQL for each of the ten report metrics.
-- The revised SQL counts conflicts, missing keys, NULLs and invalid numbers.
-- It withholds a complete candidate total when those checks are unresolved.
-- Original historical queries remain in Git history for traceability.
SELECT 'Use grain-review/COPY_CELLS.md; run cells 1-6, then cell 7 for the exact diagnostic SQL.' AS next_step;
