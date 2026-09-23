%python
from collections import defaultdict, Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D

TARGET_SVVD = ""  # Enter the full service-vessel-voyage and direction.
CUSTOMER = None   # Optional exact customer name from booking detail.
REQUEST_TIMEZONE = None  # Set only when the submission field's timezone is confirmed.
MAX_SHIPMENTS = 10000
CHART_ROWS = 25


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def parse_request_time(raw, zone_name=None):
    if raw is None or not str(raw).strip():
        return None, "MISSING_SUBMISSION_TIME"
    value = str(raw).strip()
    compact = re.fullmatch(
        r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?",
        value, flags=re.I
    )
    if compact:
        y, mo, d, h, mi, sec, fraction, offset = compact.groups()
        value = f"{y}-{mo}-{d}T{h}:{mi}:{sec}{fraction or ''}{offset or ''}"
    if not re.search(r"[T ]\d{2}:\d{2}", value):
        return None, "DATE_ONLY_OR_UNSUPPORTED_FORMAT"
    try:
        parsed = datetime.fromisoformat(re.sub(r"[zZ]$", "+00:00", value))
    except ValueError:
        return None, "UNPARSED_SUBMISSION_TIME"
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc), "EXPLICIT_OFFSET"
    if not zone_name:
        return None, "SUBMISSION_TIMEZONE_UNCONFIRMED"
    zone = ZoneInfo(zone_name)
    first = parsed.replace(tzinfo=zone, fold=0)
    second = parsed.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None, "AMBIGUOUS_OR_NONEXISTENT_LOCAL_TIME"
    if first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != parsed:
        return None, "NONEXISTENT_LOCAL_TIME"
    return first.astimezone(timezone.utc), "CONFIGURED_TIMEZONE"


def build_cohort_sql(target, customer=None):
    customer_filter = "1 = 1" if not customer else "customer = " + literal(customer)
    return f"""
    WITH normalized AS (
      SELECT
        NULLIF(UPPER(TRIM(shipment_num)), '') AS shipment_num,
        TRIM(ccp_cus_nme) AS customer,
        TRIM(agmt_num) AS agreement,
        UPPER(TRIM(lpol_port_cde)) AS loading_port,
        CASE WHEN SUBSTRING(UPPER(TRIM(corp_voy_dir)), 1, 1) IN ('N','S','E','W')
          THEN CONCAT(REGEXP_REPLACE(UPPER(TRIM(corp_svc_cde)), '-[NSEW]$', ''),
            '-', UPPER(TRIM(corp_vsl_cde)), '-',
            CASE WHEN LENGTH(TRIM(corp_voy_num)) < 3
              THEN LPAD(UPPER(TRIM(corp_voy_num)), 3, '0')
              ELSE UPPER(TRIM(corp_voy_num)) END,
            ' ', SUBSTRING(UPPER(TRIM(corp_voy_dir)), 1, 1)) END AS svvd,
        COALESCE(rec_upd_dt_utc, rec_cre_dt_utc) AS updated_at
      FROM datasources.csal.csal_booking_detail
      WHERE shipment_num IS NOT NULL
    ), ranked AS (
      SELECT *, DENSE_RANK() OVER (
        PARTITION BY shipment_num ORDER BY updated_at DESC NULLS LAST
      ) AS revision_rank
      FROM normalized WHERE shipment_num IS NOT NULL
    ), latest AS (
      SELECT DISTINCT shipment_num, customer, agreement, loading_port, svvd
      FROM ranked WHERE revision_rank = 1
    ), counted AS (
      SELECT *, COUNT(*) OVER (PARTITION BY shipment_num) AS context_variants
      FROM latest
    ), selected AS (
      SELECT shipment_num, MAX(customer) AS customer, MAX(agreement) AS agreement,
        MAX(loading_port) AS loading_port, MAX(context_variants) AS context_variants
      FROM counted
      WHERE svvd = {literal(target)} AND {customer_filter}
      GROUP BY shipment_num
    ), shipment_times AS (
      SELECT UPPER(TRIM(s.shipment_number)) AS shipment_num,
        COUNT(*) AS source_rows,
        COUNT(DISTINCT s.rec_cre_dt_utc) AS time_values,
        SUM(CASE WHEN s.rec_cre_dt_utc IS NULL THEN 1 ELSE 0 END) AS null_times,
        MIN(UNIX_MICROS(s.rec_cre_dt_utc)) AS record_created_us
      FROM datasources.csal.csal_shipment s
      INNER JOIN selected c ON UPPER(TRIM(s.shipment_number)) = c.shipment_num
      GROUP BY UPPER(TRIM(s.shipment_number))
    )
    SELECT c.*, s.source_rows, s.time_values, s.null_times,
      CASE WHEN s.time_values = 1 AND s.null_times = 0 AND c.context_variants = 1
        THEN s.record_created_us END AS record_created_us
    FROM selected c LEFT JOIN shipment_times s ON s.shipment_num = c.shipment_num
    ORDER BY c.shipment_num
    LIMIT {MAX_SHIPMENTS + 1}
    """


def build_request_sql(cohort_view):
    return f"""
    WITH requests AS (
      SELECT DISTINCT
        CAST(id AS STRING) AS source_id,
        NULLIF(TRIM(request_id), '') AS request_id,
        NULLIF(UPPER(TRIM(shipment_num)), '') AS direct_shipment,
        NULLIF(REGEXP_REPLACE(UPPER(TRIM(svvd)), ' +', ' '), '') AS request_svvd,
        NULLIF(UPPER(TRIM(load_port)), '') AS request_port,
        request_action, request_status, actual_bkg_ind,
        request_submission_date AS submission_raw,
        CAST(version_number AS STRING) AS version_number
      FROM datasources.csal.csal_shp_external_rqst
    ), refs AS (
      SELECT DISTINCT NULLIF(TRIM(request_id), '') AS request_id,
        NULLIF(UPPER(TRIM(shipment_num)), '') AS reference_shipment
      FROM datasources.csal.csal_shp_external_rqst_ref
    ), candidates AS (
      SELECT r.request_id, c.shipment_num
      FROM requests r INNER JOIN {cohort_view} c
        ON r.direct_shipment = c.shipment_num
      WHERE r.request_id IS NOT NULL
      UNION
      SELECT r.request_id, c.shipment_num
      FROM refs r INNER JOIN {cohort_view} c
        ON r.reference_shipment = c.shipment_num
      WHERE r.request_id IS NOT NULL
    ), all_links AS (
      SELECT r.request_id, r.direct_shipment AS shipment_num
      FROM requests r INNER JOIN (SELECT DISTINCT request_id FROM candidates) k
        ON r.request_id = k.request_id
      WHERE r.direct_shipment IS NOT NULL
      UNION
      SELECT r.request_id, r.reference_shipment AS shipment_num
      FROM refs r INNER JOIN (SELECT DISTINCT request_id FROM candidates) k
        ON r.request_id = k.request_id
      WHERE r.reference_shipment IS NOT NULL
    ), link_counts AS (
      SELECT request_id, COUNT(DISTINCT shipment_num) AS linked_shipments
      FROM all_links GROUP BY request_id
    )
    SELECT p.shipment_num, p.request_id, n.linked_shipments,
      r.source_id, r.direct_shipment, r.request_svvd, r.request_port,
      r.request_action, r.request_status, r.actual_bkg_ind,
      r.submission_raw, r.version_number
    FROM candidates p
    LEFT JOIN link_counts n ON n.request_id = p.request_id
    LEFT JOIN requests r ON r.request_id = p.request_id
    ORDER BY p.shipment_num, p.request_id, r.source_id
    LIMIT 100001
    """


def evaluate_request(rows, shipment, target, zone_name=None):
    raw_times = sorted({str(r['submission_raw']).strip() for r in rows
                        if r['submission_raw'] is not None and str(r['submission_raw']).strip()})
    result = {"raw_times": raw_times, "time": None, "status": None}
    if shipment['context_variants'] != 1:
        result['status'] = 'CURRENT_ROUTE_OR_CUSTOMER_UNRESOLVED'
    elif any(r['linked_shipments'] != 1 for r in rows):
        result['status'] = 'MULTIPLE_OR_CONFLICTING_SHIPMENT_LINKS'
    elif not any(r['direct_shipment'] == shipment['shipment_num'] for r in rows):
        result['status'] = 'REFERENCE_ONLY_LINK_UNCONFIRMED'
    elif not rows or any(r['source_id'] is None for r in rows):
        result['status'] = 'REQUEST_RECORD_MISSING'
    elif any(r['request_svvd'] != target or not r['request_port']
             or r['request_port'] != shipment['loading_port'] for r in rows):
        result['status'] = 'REQUEST_ROUTE_DIFFERENT_OR_UNRESOLVED'
    elif len(raw_times) != 1 or any(not r['submission_raw'] for r in rows):
        result['status'] = 'MISSING_OR_CONFLICTING_SUBMISSION_TIMES'
    else:
        result['time'], result['status'] = parse_request_time(raw_times[0], zone_name)
    return result


def run_timeline():
    target = ' '.join(TARGET_SVVD.upper().split())
    if not re.fullmatch(r'[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+ [NSEW]', target):
        raise ValueError('Set TARGET_SVVD to the full service-vessel-voyage and direction from your data.')
    if REQUEST_TIMEZONE:
        ZoneInfo(REQUEST_TIMEZONE)

    cohort_df = spark.sql(build_cohort_sql(target, CUSTOMER))
    cohort_rows = cohort_df.collect()
    if len(cohort_rows) > MAX_SHIPMENTS:
        raise ValueError('Too many shipments for this timeline. Set CUSTOMER to narrow it.')
    if not cohort_rows:
        print('No current shipment records match this vessel voyage and customer filter.')
        return
    shipments = {r['shipment_num']: r.asDict() for r in cohort_rows}
    view_name = 'request_timeline_' + uuid4().hex[:10]
    try:
        spark.createDataFrame(cohort_rows, schema=cohort_df.schema).createOrReplaceTempView(view_name)
        request_rows = spark.sql(build_request_sql(view_name)).collect()
    finally:
        spark.catalog.dropTempView(view_name)
    if len(request_rows) > 100000:
        raise ValueError('Too many request versions. Set CUSTOMER to narrow the timeline.')

    groups = defaultdict(list)
    for row in request_rows:
        row = row.asDict()
        groups[(row['shipment_num'], row['request_id'])].append(row)
    candidates = defaultdict(list)
    evidence = []
    for (number, request_id), rows in groups.items():
        result = evaluate_request(rows, shipments[number], target, REQUEST_TIMEZONE)
        evidence.append((number, request_id, result['status'], ' | '.join(result['raw_times'])))
        if result['time']:
            candidates[number].append((result['time'], request_id))

    timeline = []
    for number, shipment in shipments.items():
        timed = sorted(candidates[number])
        first_request, request_id = timed[0] if timed else (None, None)
        created = (datetime.fromtimestamp(shipment['record_created_us'] / 1_000_000,
                                         tz=timezone.utc)
                   if shipment['record_created_us'] is not None else None)
        timeline.append({
            'shipment_num': number,
            'customer': shipment['customer'] if shipment['context_variants'] == 1 else '[ambiguous current context]',
            'agreement': shipment['agreement'],
            'earliest_timed_request_utc': first_request,
            'request_id': request_id,
            'shipment_record_created_utc': created,
            'timed_requests_available': len(timed),
            'request_after_record_creation': bool(first_request and created and first_request > created)
        })

    both = sum(bool(r['earliest_timed_request_utc'] and r['shipment_record_created_utc']) for r in timeline)
    print(f"{target} | {len(timeline):,} current shipments | {both:,} with both timestamp candidates")
    print('Booking time is not yet confirmed. The red marker is CSAL shipment-record creation.')
    if evidence:
        statuses = Counter(r[2] for r in evidence)
        print('Request checks: ' + '; '.join(f'{k}: {v}' for k, v in sorted(statuses.items())))
    else:
        print('No request IDs were linked through the available direct or reference records.')

    table_rows = [(r['customer'] or '', r['shipment_num'], r['agreement'] or '',
                   r['request_id'] or '',
                   r['earliest_timed_request_utc'].isoformat() if r['earliest_timed_request_utc'] else '',
                   r['shipment_record_created_utc'].isoformat() if r['shipment_record_created_utc'] else '',
                   r['timed_requests_available'], r['request_after_record_creation']) for r in timeline]
    display(spark.createDataFrame(table_rows, 'customer STRING, shipment_num STRING, agreement STRING, '
        'request_id STRING, earliest_available_timed_request_utc STRING, shipment_record_created_utc STRING, '
        'timed_requests_available INT, request_after_record_creation BOOLEAN'))
    if evidence:
        display(spark.createDataFrame(evidence,
            'shipment_num STRING, request_id STRING, request_check STRING, submission_time_raw STRING'))

    with_times = [r for r in timeline if r['earliest_timed_request_utc'] or r['shipment_record_created_utc']]
    with_times.sort(key=lambda r: (r['customer'] or '', r['shipment_num']))
    shown = with_times[:CHART_ROWS]
    if not shown:
        print('No unambiguous UTC timestamps are available to plot. See the request checks above.')
        return

    fig, ax = plt.subplots(figsize=(14, max(4, 0.38 * len(shown) + 2)))
    for y, row in enumerate(shown):
        request_time = row['earliest_timed_request_utc']
        record_time = row['shipment_record_created_utc']
        if request_time and record_time:
            ax.plot([request_time, record_time], [y, y], color='#B9BEC5', linewidth=1)
        if request_time:
            ax.scatter(request_time, y, color='#203C60', marker='o', s=38, zorder=3)
        if record_time:
            ax.scatter(record_time, y, color='#D00B2E', marker='D', s=35, zorder=3)
    ax.set_yticks(range(len(shown)))
    ax.set_yticklabels([f"{(r['customer'] or 'Unknown')[:45]} | {r['shipment_num']}" for r in shown])
    ax.invert_yaxis()
    ax.set_title(f'Available request and shipment-record dates | {target}')
    ax.set_xlabel('UTC date')
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=timezone.utc))
    ax.grid(axis='x', alpha=0.2)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(handles=[
        Line2D([], [], color='#203C60', marker='o', linestyle='None', label='Earliest available timed request'),
        Line2D([], [], color='#D00B2E', marker='D', linestyle='None', label='Shipment record created')
    ], loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)
    fig.tight_layout()
    plt.show()
    plt.close(fig)
    print(f'Showing {len(shown)} of {len(with_times)} shipments with plottable timestamps, ordered by customer and shipment.')
    print('Current vessel assignment is not historical assignment. Missing request dates stay missing; '
          'submission dates may describe amendments. Connecting markers does not confirm a booking lead time.')


run_timeline()
