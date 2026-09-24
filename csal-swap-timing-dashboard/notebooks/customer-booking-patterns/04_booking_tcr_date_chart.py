# Paste into ONE Databricks Python cell after the booking clock comparison.
# Reuses saved pandas results only: no Spark actions, source queries, or writes.
import textwrap
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

_BT_DAY_US = 86_400_000_000
_BT_NAVY = '#203C60'
_BT_RED = '#CF102D'


def _bt_inputs():
    selection = globals().get('CSAL_CUSTOMER_SELECTION')
    status = globals().get('CSAL_BOOKING_STATUS_CHECK')
    if not isinstance(selection, dict) or selection.get('status') != 'SELECTED':
        raise ValueError('The completed top-25 customer selection is required.')
    if not isinstance(status, dict) or status.get('status') != 'COMPLETED':
        raise ValueError('The completed booking-status cohort is required.')
    customers, profiles, cohort = (selection.get('customers'),
                                   selection.get('selected_profiles'), status.get('cohort'))
    required_customers = {'rank', 'customer_key', 'customer', 'included_bookings'}
    required_profiles = {'customer_key', 'service', 'timing_group', 'bookings'}
    required_cohort = {'shipment_num', 'customer_key', 'service', 'booked_at_us', 'cutoff_us'}
    if (not isinstance(customers, pd.DataFrame) or not required_customers.issubset(customers.columns)
        or not isinstance(profiles, pd.DataFrame) or not required_profiles.issubset(profiles.columns)
        or not isinstance(cohort, pd.DataFrame) or not required_cohort.issubset(cohort.columns)):
        raise ValueError('Saved selection or booking columns are missing.')
    customers, profiles, cohort = customers.copy(), profiles.copy(), cohort.copy()
    if (len(customers) != 25 or customers.customer_key.isna().any()
        or customers.customer_key.duplicated().any()
        or sorted(customers['rank'].tolist()) != list(range(1, 26))):
        raise ValueError('Expected 25 uniquely ranked customers from the saved selection.')
    if (cohort.empty or cohort.shipment_num.isna().any() or cohort.shipment_num.duplicated().any()
        or cohort[['customer_key', 'service']].isna().any().any()
        or profiles.duplicated(['customer_key', 'service']).any()):
        raise ValueError('Saved booking or customer-service keys are empty or repeated.')
    expected = profiles.set_index(['customer_key', 'service']).bookings.rename('expected')
    actual = cohort.groupby(['customer_key', 'service']).size().rename('actual')
    checked = pd.concat([expected, actual], axis=1)
    if (checked.isna().any().any() or not checked.expected.eq(checked.actual).all()
        or set(profiles.customer_key) != set(customers.customer_key)):
        raise ValueError('The saved cohort does not match every selected customer-service profile.')
    by_customer = cohort.groupby('customer_key').size()
    totals = customers.set_index('customer_key').included_bookings
    if not by_customer.reindex(totals.index).eq(totals).all():
        raise ValueError('The saved top-25 customer totals no longer reconcile.')
    for column in ['booked_at_us', 'cutoff_us']:
        numeric = pd.to_numeric(cohort[column], errors='coerce')
        if numeric.isna().any() or (numeric < 0).any() or (numeric % 1 != 0).any():
            raise ValueError(column + ' must contain valid UTC epoch microseconds for every booking.')
        cohort[column] = numeric.astype('int64')
    settings = selection.get('settings', {})
    before, after = int(settings['days_before']), int(settings['days_after'])
    if before < 0 or after < 0 or before + after == 0:
        raise ValueError('The saved TCR comparison window is invalid.')
    proxy_day = cohort.booked_at_us // _BT_DAY_US - cohort.cutoff_us // _BT_DAY_US
    if not proxy_day.between(-before, after).all():
        raise ValueError('The saved booking cohort falls outside its selected comparison window.')
    return selection, status, customers.sort_values('rank'), profiles, cohort, proxy_day, before, after


def _bt_source_days(selection, status, cohort, proxy_day):
    # The unsuffixed timeline clock carries no timezone. Use it only when the
    # saved comparison agrees and every selected UTC calendar date matches.
    timeline = globals().get('CSAL_TIMELINE_COVERAGE_CHECK')
    comparison = globals().get('CSAL_BOOKING_CLOCK_COMPARISON')
    fallback = ('csal_shipment.rec_cre_dt_utc (shipment-record creation date proxy)',
                'Timeline UTC interpretation was not supported for every selected booking.')
    if (not isinstance(timeline, dict) or timeline.get('status') != 'COMPLETED'
        or timeline.get('_source_ref') is not status
        or timeline.get('_selection_ref') is not selection
        or not isinstance(comparison, dict) or comparison.get('status') != 'COMPLETED'):
        return proxy_day, *fallback
    matched, summary = timeline.get('matched'), comparison.get('summary')
    if (not isinstance(matched, pd.DataFrame)
        or not {'shipment_num', 'bkg_cre_iodt'}.issubset(matched.columns)
        or matched.shipment_num.isna().any() or matched.shipment_num.duplicated().any()
        or len(matched) != len(cohort)
        or set(matched.shipment_num) != set(cohort.shipment_num)
        or not isinstance(summary, pd.DataFrame) or len(summary) != 1):
        return proxy_day, *fallback
    raw = cohort.shipment_num.map(matched.set_index('shipment_num').bkg_cre_iodt).astype('string').str.strip()
    parts = raw.str.extract(r'^(?P<whole>\d{14})(?:\.(?P<fraction>\d{1,9}))?$')
    compact = parts['whole'] + '.' + parts['fraction'].fillna('').str.ljust(6, '0').str[:6]
    clock = pd.to_datetime(compact, format='%Y%m%d%H%M%S.%f', errors='coerce')
    if clock.isna().any():
        return proxy_day, *fallback
    assumed_utc = clock.dt.tz_localize('UTC')
    record_utc = pd.to_datetime(cohort.booked_at_us, unit='us', utc=True, errors='coerce')
    cutoff_utc = pd.to_datetime(cohort.cutoff_us, unit='us', utc=True, errors='coerce')
    if record_utc.isna().any() or cutoff_utc.isna().any():
        return proxy_day, *fallback
    same_date = assumed_utc.dt.normalize().eq(record_utc.dt.normalize())
    within_five = assumed_utc.sub(record_utc).abs().le(pd.Timedelta(minutes=5))
    timeline_day = (assumed_utc.dt.normalize() - cutoff_utc.dt.normalize()).dt.days
    crossing = (np.sign(timeline_day) != np.sign(proxy_day)).sum()
    observed = {
        'selected_bookings': len(cohort), 'comparable_bookings': len(cohort),
        'missing_or_unparsed': 0, 'within_5_minutes': int(within_five.sum()),
        'same_calendar_date': int(same_date.sum()),
        'different_calendar_date': int((~same_date).sum()),
        'changed_before_on_after_bucket': int(crossing),
    }
    try:
        comparison_agrees = all(int(summary.iloc[0][key]) == value for key, value in observed.items())
    except (KeyError, TypeError, ValueError, OverflowError):
        comparison_agrees = False
    if (not comparison_agrees or not same_date.all()
        or crossing or not timeline_day.eq(proxy_day).all()):
        return proxy_day, *fallback
    return (timeline_day,
            'timeline bkg_cre_iodt (UTC assumed; date agrees with shipment record)',
            f'All 25 customers have unique timeline matches; {int(within_five.sum()):,} '
            f'of {len(cohort):,} clocks are within 5 minutes, and all are on the same '
            'UTC date as the shipment-record clock. This agreement does not prove the '
            'timeline field timezone or business-event meaning.')


def _bt_draw(customers, customer_daily, before, after, source):
    days = np.arange(-before, after + 1)
    ticks = sorted(set([-before, 0, after]))
    with plt.rc_context({'font.family': 'DejaVu Sans', 'figure.facecolor': 'white',
                         'axes.facecolor': 'white'}):
        fig, axes = plt.subplots(5, 5, figsize=(17.5, 13), sharex=True, squeeze=False)
        for ax, row in zip(axes.flat, customers.itertuples(index=False)):
            part = customer_daily.loc[customer_daily.customer_key.eq(row.customer_key)]
            series = part.set_index('day_from_cutoff').bookings.reindex(days, fill_value=0)
            ax.plot(days, series.to_numpy(), color=_BT_NAVY, linewidth=1.5)
            ax.axvline(0, color=_BT_RED, linewidth=1.1, linestyle='--')
            name = textwrap.shorten(str(row.customer), width=56, placeholder='…')
            name = '\n'.join(textwrap.wrap(name, width=28, break_long_words=False))
            ax.set_title(f'{row.rank}. {name}\n{int(row.included_bookings):,} bookings',
                         fontsize=8.7, loc='left', color=_BT_NAVY, pad=6)
            ax.set_xlim(-before, after)
            ax.set_ylim(bottom=0)
            ax.set_xticks(ticks)
            ax.yaxis.set_major_locator(MaxNLocator(nbins=3, integer=True))
            ax.grid(axis='y', color='#E1E5EA', linewidth=.6)
            ax.set_axisbelow(True)
            ax.tick_params(labelsize=7.5, colors='#485569')
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines[['left', 'bottom']].set_color('#C5CDD6')
        fig.suptitle('Top 25 booking timestamp dates around TCR cutoff',
                     x=.045, y=.995, ha='left', fontsize=18, color=_BT_NAVY)
        fig.text(.045, .971, 'Daily counts by UTC calendar date · one panel per customer, all services combined',
                 fontsize=10, color='#485569')
        fig.text(.045, .953, 'Source: ' + source, fontsize=9, color='#485569')
        fig.supxlabel('UTC calendar days from TCR cutoff (0 = same date)', fontsize=11, y=.035)
        fig.supylabel('Selected bookings on that date', fontsize=11, x=.005)
        fig.text(.045, .009, 'Red line = cutoff date. Day 0 does not establish whether the timestamp preceded the cutoff time. '
                 'Y scales vary by customer. Customer-service group labels are in the table above.',
                 fontsize=8.5, color='#485569')
        fig.tight_layout(rect=[.025, .06, 1, .935], w_pad=1.1, h_pad=1.5)
        plt.show()
        plt.close(fig)


def run_csal_booking_tcr_date_chart():
    globals()['CSAL_BOOKING_TCR_DATE_CHART'] = None
    selection, status, customers, profiles, cohort, proxy_day, before, after = _bt_inputs()
    days, source, decision = _bt_source_days(selection, status, cohort, proxy_day)
    if not days.between(-before, after).all():
        raise ValueError('Chosen date source falls outside the selected TCR comparison window.')
    daily = (cohort[['customer_key', 'service']].assign(day_from_cutoff=days.to_numpy())
             .groupby(['customer_key', 'service', 'day_from_cutoff'], as_index=False)
             .size().rename(columns={'size': 'bookings'}))
    profile_counts = daily.groupby(['customer_key', 'service']).bookings.sum()
    if not profile_counts.reindex(profiles.set_index(['customer_key', 'service']).index).eq(
            profiles.set_index(['customer_key', 'service']).bookings).all():
        raise ValueError('Daily counts do not reconcile to the selected service profiles.')
    customer_daily = daily.groupby(['customer_key', 'day_from_cutoff'], as_index=False).bookings.sum()
    labels = profiles.merge(customers[['rank', 'customer_key', 'customer']],
                            on='customer_key', how='left', validate='many_to_one')
    labels = labels.sort_values(['rank', 'service'])[
        ['rank', 'customer', 'service', 'timing_group', 'bookings']]
    print('BEGIN CSAL TOP-25 BOOKING VS TCR DATE CHART')
    print('Source: ' + source)
    print('Clock decision: ' + decision)
    print(f'Saved cohort: {len(cohort):,} bookings; 25 ranked customers; '
          f'{len(profiles)} customer-service profiles. No source query was run.')
    print('Day 0 is the same UTC calendar date as TCR, not proof that the timestamp preceded the cutoff time.')
    print('Rank and group labels by service (groups are not assigned to combined-service curves):')
    print(labels.to_csv(sep='\t', index=False).rstrip())
    _bt_draw(customers, customer_daily, before, after, source)
    print('END CSAL TOP-25 BOOKING VS TCR DATE CHART')
    return {'status': 'COMPLETED', 'source': source, 'clock_decision': decision,
            'daily_by_service': daily, 'daily_by_customer': customer_daily,
            'service_labels': labels, 'as_of': selection['as_of'],
            'day_basis': 'UTC calendar date', 'settings': dict(selection['settings'])}


CSAL_BOOKING_TCR_DATE_CHART = run_csal_booking_tcr_date_chart()
