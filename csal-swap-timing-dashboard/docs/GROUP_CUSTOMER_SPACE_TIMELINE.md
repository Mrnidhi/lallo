# Customer groups, booking timing and extra-space requests

## Run this file

Inside the Windows VM, open a Databricks notebook. Set one cell to **Python**, copy the entire contents of [csal-group-customer-space-timeline.py](../notebooks/csal-group-customer-space-timeline.py), and run it. Do not paste it into a SQL cell.

If the earlier customer-group notebook has already run in this session, this cell uses its `CUSTOMER_RESULTS` and `CUSTOMER_TIMING` objects. It keeps the existing group labels. If those objects are absent, it rebuilds the booking profiles and uses the same grouping method from source. It does not require old temporary views or any other file import.

The cell contains no Spark cache, persist or unpersist calls. It reads the source tables, creates temporary session views for the cutoff join, and removes those views when finished. It does not change source tables or compute settings. It requires the same Spark, pandas, NumPy, Matplotlib and scikit-learn libraries as the customer-group notebook.

## What appears

**Booking-creation comparison chart:** one row per customer and service, carrying its existing G1, G2, G3 or other group label. Navy shows the middle 50% and median booking day relative to TCR day zero.

**Requested-space comparison chart:** a separate figure with the same customer order and TCR day-zero axis. Red shows the middle 50% and median day of recorded increases to requested space. Its right-hand column shows minimum, median and maximum added TEU and resulting requested total TEU, with the count of timed increases out of all qualifying increases. Long lists use several pages to keep customer names readable.

**Individual customer charts:** two separate figures: the exact daily booking curve, then individual extra-space increases. They use the same TCR day-zero scale. Each red dot in the requested-space figure is an edit; its height is added TEU. Empty days in the booking curve are zero-filled. A missing request timeline is labelled as unavailable, not drawn as zero demand. Bookings and requests are never combined within a figure.

**Supporting tables:** customer statistics, exact request records and timing exclusions, plan-cutoff evidence, and daily booking counts. A tab-separated summary appears between `BEGIN CUSTOMER TIMELINE RESULTS` and `END CUSTOMER TIMELINE RESULTS` for easy copying.

## Change the selection

| Setting | Default | Meaning |
|---|---|---|
| `TOP_CUSTOMERS` | `25` | The 25 distinct customers with the largest included booking counts across the selected services and all their groups. Not 25 per group. |
| `SELECT_SERVICES` | `None` | All services in the prepared population. Set a list to restrict the charts. |
| `SELECT_CUSTOMERS` | `None` | Optional list of exact names. Overrides the top-25 ranking; case and extra spaces are ignored. |
| `AUDIT_TIMEZONE` | `"UTC"` | The audit timezone confirmed by the user on September 23, 2026. Explicit offsets in individual timestamps take precedence. |
| `ROWS_PER_PAGE` | `12` | Customer/service rows per comparison figure. A customer on several services has separate rows. |
| `SHOW_FIRST_CUSTOMER` | `True` | Shows the first selected customer’s two separate detailed figures immediately. |
| `SHOW_TABLES` | `True` | Shows the full evidence tables after the charts. |
| `REBUILD_GROUPS` | `False` | Keeps existing groups when available. Set `True` to refresh the population and groups. |

After the cell runs, change the individual chart with a short Python cell:

```python
show_group_customer("Customer name from the results", "SERVICE_CODE")
```

This switches the two detail charts without querying the source again. To include a customer outside the selected list, change `SELECT_CUSTOMERS` at the top and rerun the main cell.

`YEAR`, `SOURCE_SERVICES`, `DAYS_BEFORE`, `DAYS_AFTER`, and the grouping thresholds apply **only when rebuilding**. Existing groups keep their original population settings, which the cell prints. To expand an earlier single-service population to all services, use `REBUILD_GROUPS = True` and `SOURCE_SERVICES = None`. A refresh can change group membership as the data changes.

Group numbers belong to a service: G1 has the earliest typical booking time within that service. The code does not assume every service has three groups, or that G2 means the same day range on every service. It retains the earlier minimum of 20 bookings across three voyages for grouping unless changed during a rebuild. Customers with insufficient history are not given invented group labels.

## Definitions

- Booking time is `csal_shipment.rec_cre_dt_utc`, confirmed by the user as original booking time. The booking curve counts distinct shipments, using the same route, cutoff and observed-window rules as the existing customer-group analysis.
- Extra space is a direct, named-user `grid edit` or `multi edit` that increases `requestedTeu` from an existing nonnegative numeric value. For example, 4 to 7 TEU contributes **3 added TEU** and a **7 TEU resulting requested total**.
- Initial values, reductions, unchanged values, system edits and workflow copies are excluded. Adjusted, submitted and reviewed fields are not added to the same request count. Reversals followed by new increases remain gross edit activity; these are not net allocations or fulfilled demand.
- Min/median/max are calculated per qualifying edit, not from daily totals. Comparison-chart quantity statistics cover qualifying edits in the recorded year for the selected customer/service, including edits without usable cutoff timing. Red timing ranges use only the mapped edits inside the displayed window. The individual-chart TEU caption describes its timed subset. These denominators are shown separately.
- Day zero starts at the cutoff timestamp. Daily bins are 24-hour intervals relative to that instant, not local calendar dates. With defaults the window is −56 inclusive to +14 exclusive. Requests after cutoff remain eligible within that window.
- Customer names are matched by case and whitespace only. No fuzzy merging of unrelated names is performed. Plan history must have consistent customer and service identity before its edits are attributed.

## How a request receives a cutoff

The code reads current `csal_booking_assoc_evt` links for the request plan and joins them to the available booking-route evidence. It rejects conflicting latest rows, non-matching flags, shipments matched to multiple plans, customer/service/voyage mismatches, incomplete routes, unavailable calls and missing booking evidence. Every available plan link must resolve to the same voyage, loading port and cutoff. Multiple ports or cutoffs remain unresolved; the code never chooses an arbitrary first or last cutoff.

The bridge contains one row per plan before it joins to the audit events. Several bookings linked to one plan cannot multiply the request count or TEU. The matching is deliberately conservative: a plan with no remaining bookings or an older linked booking outside the prepared population may have no usable reference.

The resulting request axis is **relative to the latest linked TCR cutoff**. Current associations and cutoffs do not reconstruct their historical values at the request date. Recorded requested-TEU edits also do not prove that the customer personally submitted a request. Unresolved edits remain in the evidence and quantity results instead of being placed at day zero.

## Delivery and validation

The deliverable is code, not a production result export. Local checks use synthetic rows to exercise customer selection, grouping preservation, request quantities, timing boundaries, duplicate handling, cutoff joins and chart rendering. Run the cell in Databricks to obtain the real charts and coverage. No live results are claimed by the Git commit.

For maintenance, `scripts/build_group_space_cell.py` bundles shared SQL, grouping helpers, `group_space_timeline_core.py` and `group_space_chart_helpers.py` into the single paste-ready file. The helper files are not additional cells for the user to run.
