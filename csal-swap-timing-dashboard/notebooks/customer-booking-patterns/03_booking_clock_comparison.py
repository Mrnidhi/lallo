# Databricks Python cell. Run after CSAL_TIMELINE_COVERAGE_CHECK.
# Compares saved booking clocks; runs no new source query or Spark action.
import pandas as pd


def run_csal_booking_clock_comparison():
    prior = globals().get('CSAL_TIMELINE_COVERAGE_CHECK')
    if not isinstance(prior, dict) or prior.get('status') != 'COMPLETED':
        raise ValueError('Run the timeline coverage cell successfully first.')
    matched = prior.get('matched')
    required = {'shipment_num', 'bkg_cre_iodt', 'booked_at_us'}
    if not isinstance(matched, pd.DataFrame) or not required.issubset(matched.columns):
        raise ValueError('The saved selected bookings are missing required columns.')
    if matched.empty or matched.shipment_num.isna().any() or matched.shipment_num.duplicated().any():
        raise ValueError('Selected shipment numbers are empty, missing or repeated.')

    # The timeline coverage cell kept booking creation time but did not carry
    # cutoff_us into matched. Restore it from the saved booking-status cohort.
    booking_status = globals().get('CSAL_BOOKING_STATUS_CHECK')
    if not isinstance(booking_status, dict) or booking_status.get('status') != 'COMPLETED':
        raise ValueError('Run the booking-status check successfully first.')
    cohort = booking_status.get('cohort')
    if (not isinstance(cohort, pd.DataFrame)
        or not {'shipment_num', 'booked_at_us', 'cutoff_us'}.issubset(cohort.columns)
        or cohort.shipment_num.isna().any() or cohort.shipment_num.duplicated().any()):
        raise ValueError('The saved booking-status cohort is missing unique booking and cutoff keys.')
    compared = matched[['shipment_num', 'bkg_cre_iodt', 'booked_at_us']].merge(
        cohort[['shipment_num', 'booked_at_us', 'cutoff_us']], on='shipment_num',
        how='left', validate='one_to_one', suffixes=('', '_cohort'))
    if len(compared) != len(matched) or compared.cutoff_us.isna().any():
        raise ValueError('Not every timeline booking has one saved TCR cutoff.')
    if not compared.booked_at_us.eq(compared.booked_at_us_cohort).all():
        raise ValueError('The timeline and booking-status cells use different booking creation values.')

    # The compact timeline clock has no timezone suffix. Assigning UTC here is
    # only a comparison hypothesis, not a declaration of its source timezone.
    raw = compared.bkg_cre_iodt.astype('string').str.strip()
    parts = raw.str.extract(r'^(?P<whole>\d{14})(?:\.(?P<fraction>\d{1,9}))?$')
    compact = parts['whole'] + '.' + parts['fraction'].fillna('').str.ljust(6, '0').str[:6]
    clock = pd.to_datetime(compact, format='%Y%m%d%H%M%S.%f', errors='coerce')
    record = pd.to_datetime(compared.booked_at_us, unit='us', utc=True, errors='coerce')
    cutoff = pd.to_datetime(compared.cutoff_us, unit='us', utc=True, errors='coerce')
    valid = clock.notna() & record.notna() & cutoff.notna()
    if not valid.any():
        raise ValueError('No selected booking has both comparable creation clocks and a cutoff.')

    hypothesis_utc = clock.loc[valid].dt.tz_localize('UTC')
    observed_utc = record.loc[valid]
    observed_cutoff = cutoff.loc[valid]
    seconds = (hypothesis_utc - observed_utc).dt.total_seconds()
    difference_minutes = (seconds / 60).round().astype('int64')
    minute_modes = difference_minutes.value_counts().head(10).rename_axis(
        'timeline_clock_minus_shipment_record_minutes').reset_index(name='bookings')

    record_day = (observed_utc.dt.normalize() - observed_cutoff.dt.normalize()).dt.days
    clock_day = (hypothesis_utc.dt.normalize() - observed_cutoff.dt.normalize()).dt.days

    def period(days):
        return days.map(lambda day: 'Before' if day < 0 else 'After' if day > 0 else 'On date')

    old_period, candidate_period = period(record_day), period(clock_day)
    crossing = pd.crosstab(old_period, candidate_period, dropna=False).reindex(
        index=['Before', 'On date', 'After'],
        columns=['Before', 'On date', 'After'], fill_value=0)
    crossing.index.name = 'shipment_record_vs_cutoff'
    crossing.columns.name = 'timeline_clock_if_UTC_vs_cutoff'
    crossing = crossing.reset_index()

    absolute = seconds.abs()
    summary = pd.DataFrame([{
        'selected_bookings': len(matched),
        'comparable_bookings': int(valid.sum()),
        'missing_or_unparsed': int((~valid).sum()),
        'within_1_minute': int(absolute.le(60).sum()),
        'within_5_minutes': int(absolute.le(300).sum()),
        'within_1_hour': int(absolute.le(3600).sum()),
        'same_calendar_date': int(hypothesis_utc.dt.date.eq(observed_utc.dt.date).sum()),
        'different_calendar_date': int(hypothesis_utc.dt.date.ne(observed_utc.dt.date).sum()),
        'changed_before_on_after_bucket': int(old_period.ne(candidate_period).sum()),
    }])
    print('BEGIN CSAL BOOKING CLOCK COMPARISON')
    print('Comparison only: timeline bkg_cre_iodt is treated as UTC temporarily to test its agreement with csal_shipment.rec_cre_dt_utc.')
    print('Summary')
    print(summary.to_csv(sep='\t', index=False).rstrip())
    print('Ten most frequent whole-minute differences')
    print(minute_modes.to_csv(sep='\t', index=False).rstrip())
    print('Before/on/after TCR date under the two clocks')
    print(crossing.to_csv(sep='\t', index=False).rstrip())
    print('Close agreement supports a UTC interpretation but does not prove the timeline field timezone or business event meaning.')
    print('If many dates or cutoff buckets differ, keep the existing shipment-record date chart labeled as a proxy until the clock meaning is confirmed.')
    print('END CSAL BOOKING CLOCK COMPARISON')
    return {'status': 'COMPLETED', 'summary': summary,
            'minute_modes': minute_modes, 'cutoff_buckets': crossing}


CSAL_BOOKING_CLOCK_COMPARISON = run_csal_booking_clock_comparison()
