# Paste this entire file into ONE new Python cell after Main analysis cell 6.
# Uses completed results in memory. No Spark queries, table writes or regrouping.
from decimal import Decimal, InvalidOperation
from statistics import median
from time import monotonic
import math
import re
import textwrap
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

REQUEST_EDIT_WINDOW_MINUTES = 10   # Also reports the 1- and 60-minute alternatives.
REQUEST_NAVY, REQUEST_RED = '#203C60', '#CF102D'


def _rq_norm(value):
    return '' if value is None or pd.isna(value) else ' '.join(str(value).split()).upper()


def _rq_number(value):
    if value is None or pd.isna(value):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def _rq_time(value):
    if value is None or pd.isna(value):
        return pd.NaT
    # Earlier cells have already parsed the raw audit timestamp as UTC.
    value = pd.Timestamp(value)
    if value.tzinfo is None:
        raise ValueError('An audit timestamp lost its UTC timezone. Rerun cell 5, then cell 6.')
    return value.tz_convert('UTC')


def _rq_stats(values):
    numbers = sorted(x for x in values if x is not None)
    return (min(numbers), median(numbers), max(numbers)) if numbers else (None, None, None)


def _rq_format(value):
    return format(Decimal(str(value)).normalize(), 'f')


def _rq_inputs(namespace):
    requirements = [('CSAL_CUSTOMER_SELECTION', 'SELECTED', 3),
                    ('CSAL_CUTOFF_BREAKDOWN', 'COMPLETED', 5),
                    ('CSAL_SHIPMENT_LINK_CHECK', 'COMPLETED', 6)]
    missing = [f'{name}: run cell {cell}' for name, state, cell in requirements
               if not isinstance(namespace.get(name), dict) or namespace[name].get('status') != state]
    if missing:
        raise ValueError('Prepared results are missing. ' + '; '.join(missing)
                         + '. If the session restarted, run cells 1–6 in order first.')
    selection, breakdown, links = [namespace[name] for name, _, _ in requirements]
    as_of = _rq_time(selection['as_of'])
    for result in (breakdown, links):
        if _rq_time(result['booking_read_started']) != as_of:
            raise ValueError('The prepared results belong to different runs. Rerun cells 3–6 together.')
    if links.get('_breakdown_ref', breakdown) is not breakdown:
        raise ValueError('Cell 5 changed after cell 6. Rerun cell 6 before this chart.')
    if links.get('_selection_ref', selection) is not selection:
        raise ValueError('The customer selection changed after cell 6. Rerun cells 5–6.')
    customers = selection['customers'].sort_values('rank').copy()
    events = links['event_evidence'].copy()
    if customers.empty or customers.customer_key.duplicated().any():
        raise ValueError('The selected customer list is empty or duplicated.')
    if events.audit_id.isna().any() or events.audit_id.astype(str).duplicated().any():
        raise ValueError('Request audit IDs are missing or repeated.')
    if set(events.audit_id.astype(str)) != set(breakdown['events'].audit_id.astype(str)):
        raise ValueError('Cells 5 and 6 do not contain the same request edits.')
    settings = dict(selection['settings'])
    before, after = int(settings['days_before']), int(settings['days_after'])
    if before < 0 or after < 0 or before + after == 0:
        raise ValueError('The selected comparison window is invalid.')

    # Index only the relevant plans, not all 120,605 current plan rows.
    ids = set(events.plan_id.astype(str))
    plans = breakdown['plans']
    metadata = plans.loc[plans.plan_id.astype(str).isin(ids), ['plan_id', 'customer_key', 'service']].copy()
    metadata['plan_id'] = metadata.plan_id.astype(str)
    metadata = metadata.drop_duplicates()
    metadata = metadata[~metadata.plan_id.duplicated(keep=False)]
    context = metadata.set_index('plan_id').to_dict('index')
    events['plan_id'] = events.plan_id.astype(str)
    events['audit_id'] = events.audit_id.astype(str)
    events['customer_key'] = events.plan_id.map(lambda pid: context.get(pid, {}).get('customer_key'))
    events['service'] = events.plan_id.map(lambda pid: re.sub(r'-[NSEW]$', '', context.get(pid, {}).get('service', '')))
    supported = events[events.shipment_supported_candidate.eq(True)].copy()
    if not supported.customer_key.isin(customers.customer_key).all():
        raise ValueError('A supported edit has missing or conflicting customer ownership.')
    if supported.observed_date.isna().any():
        raise ValueError('A supported edit is missing its observed cutoff date.')
    return selection, breakdown, links, customers, events, supported, as_of, before, after


def _rq_histories(history, candidates, as_of):
    ids = set(candidates.plan_id)
    history = history.loc[history.plan_id.astype(str).isin(ids)].copy()
    history['plan_id'] = history.plan_id.astype(str)
    history['audit_id'] = history.audit_id.map(lambda x: '' if pd.isna(x) else str(x))
    history['event_utc'] = history.event_utc.map(_rq_time)
    # Future observations must not influence the selected run's correction checks.
    history = history[history.event_utc.isna() | (history.event_utc < as_of)].copy()
    history['old_teu'] = history.old_teu.map(_rq_number)
    history['new_teu'] = history.new_teu.map(_rq_number)
    history['id_ok'] = history.audit_id.ne('') & history.id_versions.eq(1)
    history.loc[history.audit_id.duplicated(keep=False), 'id_ok'] = False
    histories, eligibility = {}, []
    by_plan = {pid: part for pid, part in history.groupby('plan_id', sort=False)}
    for pid, part in candidates.groupby('plan_id', sort=False):
        all_rows = by_plan.get(pid, history.iloc[:0])
        requested = all_rows[all_rows.field_key.eq('requestedteu') & all_rows.direct_edit.eq(True)].copy()
        bad_history = requested.event_utc.isna().any() or not requested.id_ok.all()
        requested['time_tie'] = requested.event_utc.duplicated(keep=False)
        requested = requested.sort_values('event_utc', kind='stable')
        rows = requested.to_dict('records')
        histories[pid] = rows
        index = {row['audit_id']: row for row in rows}
        finalized = all_rows[all_rows.field_key.eq('finalized') & all_rows.action_type.eq('finalize')]
        known_finalized = finalized[finalized.id_ok & finalized.event_utc.notna()].event_utc.tolist()
        for event in part.itertuples(index=False):
            row = index.get(event.audit_id)
            old, new, when = _rq_number(event.old_teu), _rq_number(event.new_teu), _rq_time(event.event_utc)
            if row is None or bad_history or pd.isna(when) or not when < as_of:
                reason = 'DIRECT_HISTORY_UNRESOLVED'
            elif row['old_teu'] != old or row['new_teu'] != new or row['event_utc'] != when:
                raise ValueError('An audit event differs from its supporting history.')
            elif row['time_tie']:
                reason = 'SIMULTANEOUS_DIRECT_EDITS'
            elif old is None or new is None or old < 0 or new <= old:
                raise ValueError('A candidate is not a positive requested-TEU edit.')
            elif old == 0 and not any(t < when for t in known_finalized):
                reason = 'ZERO_WITHOUT_EARLIER_FINALIZATION'
            else:
                reason = 'ELIGIBLE_ZERO_AFTER_FINALIZATION' if old == 0 else 'ELIGIBLE_POSITIVE_BASE'
            eligibility.append(dict(audit_id=event.audit_id, plan_id=pid, entry_check=reason))
    return histories, pd.DataFrame(eligibility, columns=['audit_id', 'plan_id', 'entry_check'])


def _rq_episodes(candidates, histories, entry_check, as_of, minutes):
    # These are analytical edit episodes, not identified customer requests or swaps.
    allowed = set(entry_check.loc[entry_check.entry_check.str.startswith('ELIGIBLE'), 'audit_id'])
    lookup = candidates.set_index('audit_id').to_dict('index')
    window = pd.Timedelta(minutes=minutes)
    result = []
    for pid, rows in histories.items():
        consumed = set()
        for i, first in enumerate(rows):
            aid = first['audit_id']
            if aid not in allowed or aid in consumed:
                continue
            members, last, j = [aid], first, i + 1
            # Only consecutive, continuous increases by the same editor are merged.
            # Bound the whole episode, rather than allowing an indefinitely chained window.
            while j < len(rows):
                nxt = rows[j]
                if (nxt['audit_id'] not in allowed or nxt['audit_id'] in consumed
                    or _rq_norm(nxt['editor']) != _rq_norm(first['editor'])
                    or nxt['old_teu'] != last['new_teu']
                    or nxt['event_utc'] - first['event_utc'] > window):
                    break
                members.append(nxt['audit_id']); last = nxt; j += 1
            consumed.update(members)
            flag = 'KEPT'
            if last['event_utc'] + window > as_of:
                flag = 'CORRECTION_WINDOW_NOT_COMPLETE'
            value = last['new_teu']
            for nxt in rows[j:]:
                if nxt['event_utc'] - last['event_utc'] > window:
                    break
                if nxt['time_tie'] or nxt['old_teu'] is None or nxt['new_teu'] is None or nxt['old_teu'] != value:
                    flag = 'QUICK_SEQUENCE_UNRESOLVED'; break
                if nxt['new_teu'] < nxt['old_teu']:
                    flag = 'QUICK_RETURN_TO_BASELINE' if nxt['new_teu'] <= first['old_teu'] else 'QUICK_DECREASE_REVIEW'
                    break
                value = nxt['new_teu']
            # A later return may be legitimate. Flag it for review, never declare it an error.
            later_return = any(nxt['id_ok'] and not nxt['time_tie'] and nxt['new_teu'] == first['old_teu']
                               and nxt['old_teu'] is not None and nxt['old_teu'] > nxt['new_teu']
                               for nxt in rows[j:])
            if flag == 'KEPT' and later_return:
                flag = 'LATER_RETURN_REQUIRES_REVIEW'
            event = lookup[aid]
            cutoff = pd.Timestamp(event['observed_date']).date()
            result.append(dict(episode_id=aid, plan_id=pid, customer_key=event['customer_key'],
                               service=event['service'], started_at=first['event_utc'], ended_at=last['event_utc'],
                               cutoff_date=cutoff, day_from_cutoff=(first['event_utc'].date() - cutoff).days,
                               old_requested_teu=first['old_teu'], new_requested_teu=last['new_teu'],
                               added_teu=last['new_teu'] - first['old_teu'], audit_ids=tuple(members),
                               raw_edits=len(members), review_status=flag, later_return=later_return))
    columns = ['episode_id', 'plan_id', 'customer_key', 'service', 'started_at', 'ended_at', 'cutoff_date',
               'day_from_cutoff', 'old_requested_teu', 'new_requested_teu', 'added_teu', 'audit_ids',
               'raw_edits', 'review_status', 'later_return']
    output = pd.DataFrame(result, columns=columns)
    if sum(output.raw_edits) != len(allowed):
        raise ValueError('Episode counts do not reconcile to eligible original edits.')
    return output


def _rq_tables(customers, events, candidates, checks, episodes, breakdown, before, after):
    plotted = episodes.loc[episodes.review_status.eq('KEPT') & episodes.day_from_cutoff.between(-before, after)].copy()
    daily = plotted.groupby(['customer_key', 'service', 'day_from_cutoff'], as_index=False).agg(
        edit_episodes=('episode_id', 'size'), added_teu=('added_teu', 'sum'))
    coverage = breakdown['customer_coverage'].set_index('customer').to_dict('index')
    rows = []
    for c in customers.itertuples(index=False):
        raw = events[events.customer_key == c.customer_key]
        supported = candidates[candidates.customer_key == c.customer_key]
        all_episodes = episodes[episodes.customer_key == c.customer_key]
        part = plotted[plotted.customer_key == c.customer_key]
        entry_review = checks[checks.audit_id.isin(supported.audit_id) & ~checks.entry_check.str.startswith('ELIGIBLE')]
        quantity = _rq_stats(part.added_teu)
        raw_quantity = _rq_stats(all_episodes.loc[all_episodes.day_from_cutoff.between(-before, after), 'added_teu'])
        if len(part):
            status = 'Shown'
        elif coverage.get(c.customer, {}).get('coverage_status') == 'NO_CURRENT_PLAN_NAME_MATCH':
            status = 'No current plan-name match'
        elif raw.empty:
            status = 'No qualifying edits in this scope'
        elif supported.empty:
            status = 'Cutoff or context unresolved'
        elif len(all_episodes[all_episodes.review_status.eq('KEPT')]):
            status = 'Kept edits outside plotted window'
        else:
            status = 'Entry or correction review required'
        rows.append(dict(rank=c.rank, customer_key=c.customer_key, customer=c.customer,
                         scoped_raw_edits=len(raw), cutoff_candidate_edits=len(supported),
                         plotted_raw_edits=int(part.raw_edits.sum()), plotted_episodes=len(part),
                         plotted_raw_coverage_pct=round(100 * part.raw_edits.sum() / len(raw), 2) if len(raw) else None,
                         entry_review_edits=len(entry_review),
                         review_episodes=int(all_episodes.review_status.ne('KEPT').sum()),
                         kept_outside_window=int((all_episodes.review_status.eq('KEPT') & ~all_episodes.day_from_cutoff.between(-before, after)).sum()),
                         before_date=int((part.day_from_cutoff < 0).sum()), on_date=int((part.day_from_cutoff == 0).sum()),
                         after_date=int((part.day_from_cutoff > 0).sum()), median_day=median(part.day_from_cutoff) if len(part) else None,
                         min_added_teu=quantity[0], median_added_teu=quantity[1], max_added_teu=quantity[2],
                         unscreened_min_teu=raw_quantity[0], unscreened_median_teu=raw_quantity[1], unscreened_max_teu=raw_quantity[2],
                         status=status))
    return plotted, daily, pd.DataFrame(rows)


def _rq_draw(summary, daily, before, after, minutes):
    cols = min(5, len(summary)); nrows = math.ceil(len(summary) / cols)
    with plt.rc_context({'font.family': 'DejaVu Sans', 'figure.facecolor': 'white', 'axes.facecolor': 'white'}):
        fig, axes = plt.subplots(nrows, cols, figsize=(5 * cols, 4.05 * nrows + 1.5), squeeze=False)
        for ax, c in zip(axes.flat, summary.itertuples(index=False)):
            title = '\n'.join(textwrap.wrap(f'{c.rank}. {c.customer}', 36, max_lines=3, placeholder='…'))
            if c.plotted_episodes:
                title += f'\n{c.plotted_episodes} episodes · median day {c.median_day:g}'
                title += ('\nAdded TEU: min ' + _rq_format(c.min_added_teu) + ' / median '
                          + _rq_format(c.median_added_teu) + ' / max ' + _rq_format(c.max_added_teu))
                counts = daily[daily.customer_key == c.customer_key].groupby('day_from_cutoff').edit_episodes.sum()
                counts = counts.reindex(range(-before, after + 1), fill_value=0)
                ax.plot(counts.index, counts, color=REQUEST_NAVY, linewidth=1.3)
                nz = counts[counts > 0]; ax.scatter(nz.index, nz, color=REQUEST_NAVY, s=15, zorder=3)
                ax.set_ylim(0, max(1.2, counts.max() * 1.15))
            else:
                ax.text(.5, .48, '\n'.join(textwrap.wrap(c.status, 31)), ha='center', va='center',
                        transform=ax.transAxes, color='#637084', fontsize=11)
                ax.set_ylim(0, 1); ax.set_yticks([])
            ax.axvline(0, color=REQUEST_RED, linestyle='--', linewidth=1)
            ax.set_title(title, loc='left', fontsize=10, color=REQUEST_NAVY, pad=9)
            ax.text(0, -.25, f'{c.plotted_raw_edits}/{c.scoped_raw_edits} scoped edits shown after checks',
                    transform=ax.transAxes, fontsize=9, color='#637084')
            ax.set_xlim(-before, after)
            ax.set_xticks(sorted(set([-before, 0, after] + [d for d in range(-before, after + 1) if d % 14 == 0])))
            if c.plotted_episodes:
                ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
            ax.grid(axis='y', color='#E1E5EA', linewidth=.7); ax.set_axisbelow(True)
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines[['left', 'bottom']].set_color('#C5CDD6')
            ax.tick_params(labelsize=9, colors='#485569')
        for ax in list(axes.flat)[len(summary):]:
            ax.set_visible(False)
        fig.suptitle('When plan requested TEU was increased (shipment-linked subset)', x=.045, y=.997, ha='left', fontsize=20, color=REQUEST_NAVY)
        fig.text(.045, .976,
                 f'Selected customers · {int(summary.cutoff_candidate_edits.sum()):,}/{int(summary.scoped_raw_edits.sum()):,} edits have a shipment date · '
                 f'{int(summary.plotted_episodes.sum()):,} plotted episodes · red line = observed shipment TCR date',
                 fontsize=11, color='#485569')
        fig.supxlabel('UTC calendar days from observed shipment TCR date (0 = same date)', y=.043, fontsize=12)
        fig.supylabel('Edit episodes started on that relative day', x=.005, fontsize=12)
        fig.text(.045, .012, f'Current shipment links provide the reference date; historical plan cutoffs are not established. '
                 f'Same-editor continuous increases within {minutes} minutes form one episode.\n'
                 'Initial/uncertain zero entries and flagged corrections are excluded pending review. Missing evidence does not mean no requests. '
                 'Vertical scales differ; these are not confirmed swaps.', fontsize=9, color='#485569')
        fig.tight_layout(rect=[.02, .067, 1, .952], h_pad=3.0, w_pad=2)
        plt.show(); plt.close(fig)


def run_csal_request_chart():
    started = monotonic()
    globals()['CSAL_REQUEST_CHART'] = None
    print('BEGIN CSAL REQUEST CHART RESULTS', flush=True)
    try:
        selection, breakdown, links, customers, events, candidates, as_of, before, after = _rq_inputs(globals())
        minutes = REQUEST_EDIT_WINDOW_MINUTES
        if minutes not in (1, 10, 60):
            raise ValueError('Choose REQUEST_EDIT_WINDOW_MINUTES = 1, 10 or 60.')
        print('No new source queries. Using the completed cells in this session.', flush=True)
        print(f'Booking run: {selection["as_of"]} | Customers: {len(customers)} | Scoped edits: {len(events):,}')
        print(f'Shipment-supported cutoff candidates: {len(candidates):,}/{len(events):,}; this is not a confirmed plan cutoff.')
        print(f'Edits without unique current customer ownership: {int(events.customer_key.isna().sum()):,}.')
        histories, checks = _rq_histories(breakdown['audit_history'], candidates, as_of)
        alternatives, sensitivity = {}, []
        for window in (1, 10, 60):
            episodes = _rq_episodes(candidates, histories, checks, as_of, window)
            alternatives[window] = episodes
            kept = episodes[episodes.review_status.eq('KEPT')]
            sensitivity.append(dict(minutes=window, eligible_raw_edits=int(episodes.raw_edits.sum()),
                                    episodes=len(episodes), review_episodes=len(episodes) - len(kept),
                                    kept_episodes=len(kept), kept_added_teu=sum(kept.added_teu, Decimal(0))))
        episodes = alternatives[minutes]
        plotted, daily, summary = _rq_tables(customers, events, candidates, checks, episodes, breakdown, before, after)
        print(f'Plotted kept edit episodes: {len(plotted):,}; shipment-date candidates: {len(candidates):,}/{len(events):,} scoped edits.')
        def report(title, frame):
            print('\n' + title)
            print(frame.to_csv(sep='\t', index=False, na_rep='—').rstrip() if len(frame) else 'No rows.')
        report('1. Entry checks — supported cutoff candidates only', checks.groupby('entry_check', as_index=False).agg(edits=('audit_id', 'size')))
        report('2. Correction-window sensitivity — not a count of confirmed requests', pd.DataFrame(sensitivity))
        report(f'3. Review decisions at {minutes} minutes', episodes.groupby('review_status', as_index=False).agg(episodes=('episode_id', 'size'), raw_edits=('raw_edits', 'sum')))
        report('4. Customer results — TEU statistics describe plotted episodes', summary.drop(columns=['customer_key', 'unscreened_min_teu', 'unscreened_median_teu', 'unscreened_max_teu']))
        report('5. Added TEU before / after review exclusions — same date window', summary.loc[summary.cutoff_candidate_edits > 0,
               ['customer', 'unscreened_min_teu', 'unscreened_median_teu', 'unscreened_max_teu', 'min_added_teu', 'median_added_teu', 'max_added_teu']])
        largest = episodes.sort_values('added_teu', ascending=False).head(10).copy()
        largest['customer'] = largest.customer_key.map(customers.set_index('customer_key').customer)
        report('6. Ten largest episodes for review', largest[['customer', 'service', 'plan_id', 'started_at',
               'old_requested_teu', 'new_requested_teu', 'added_teu', 'review_status']])
        _rq_draw(summary, daily, before, after, minutes)
        print('\nAmounts are recorded increases in plan requested TEU (new minus old), not confirmed customer requests, total allocations or transfers.')
        print('A zero-to-positive edit needs a recorded earlier finalization; this does not prove zero allocated capacity.')
        print('Rapid decreases and later returns are review flags, not confirmed mistakes. Source requests may be incomplete.')
        print('Excluded edits and unavailable customers remain in the tables. No customer aliases or groups were changed.')
        print('A booking/request timing recommendation cannot be established from this limited subset alone.')
        print(f'Cell status: COMPLETED. Elapsed: {monotonic() - started:.1f}s.')
        return dict(status='COMPLETED', as_of=selection['as_of'], settings=dict(selection['settings']),
                    summary=summary, daily=daily, plotted=plotted, episodes=episodes,
                    entry_checks=checks, sensitivity=pd.DataFrame(sensitivity),
                    profiles=selection['selected_profiles'].copy(), edit_window_minutes=minutes,
                    cutoff_basis='Current linked shipment reference; historical plan cutoff unconfirmed')
    except Exception as exc:
        print('Cell status: FAILED. ' + str(exc), flush=True)
        raise
    finally:
        print('END CSAL REQUEST CHART RESULTS', flush=True)


CSAL_REQUEST_CHART = run_csal_request_chart()
