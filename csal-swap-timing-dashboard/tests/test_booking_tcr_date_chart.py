"""Regression check for saved profiles that already contain display columns."""

import ast
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


SOURCE = (Path(__file__).resolve().parents[1] /
          'notebooks/customer-booking-patterns/04_booking_tcr_date_chart.py')


class BookingTcrDateChart(unittest.TestCase):
    def test_existing_profile_rank_and_customer_do_not_break_chart(self):
        tree = ast.parse(SOURCE.read_text())
        self.assertIsInstance(tree.body[-1], ast.Assign)
        namespace = {}
        exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]),
                     str(SOURCE), 'exec'), namespace)

        customers = pd.DataFrame([
            {'rank': i, 'customer_key': f'CUSTOMER {i}',
             'customer': f'Correct customer {i}', 'included_bookings': 1}
            for i in range(1, 26)
        ])
        profiles = pd.DataFrame([
            {'rank': 100 + i, 'customer_key': f'CUSTOMER {i}',
             'customer': f'Stale customer {i}', 'service': 'S1',
             'timing_group': f'G{i % 3 + 1}', 'bookings': 1}
            for i in range(1, 26)
        ])
        cutoff_us = 1_780_000_000_000_000
        cohort = pd.DataFrame([
            {'shipment_num': str(i), 'customer_key': f'CUSTOMER {i}',
             'service': 'S1', 'booked_at_us': cutoff_us - 86_400_000_000,
             'cutoff_us': cutoff_us}
            for i in range(1, 26)
        ])
        namespace['CSAL_CUSTOMER_SELECTION'] = {
            'status': 'SELECTED', 'customers': customers,
            'selected_profiles': profiles, 'settings': {'days_before': 2, 'days_after': 1},
            'as_of': '2026-09-24T00:00:00Z'}
        namespace['CSAL_BOOKING_STATUS_CHECK'] = {
            'status': 'COMPLETED', 'cohort': cohort}

        with patch.object(plt, 'show') as show, redirect_stdout(StringIO()) as output:
            result = namespace['run_csal_booking_tcr_date_chart']()

        labels = result['service_labels']
        self.assertEqual(result['status'], 'COMPLETED')
        self.assertEqual(labels['rank'].tolist(), list(range(1, 26)))
        self.assertEqual(labels['customer'].tolist(),
                         [f'Correct customer {i}' for i in range(1, 26)])
        self.assertEqual(result['daily_by_customer'].bookings.sum(), 25)
        self.assertNotIn('Stale customer', output.getvalue())
        show.assert_called_once()
        self.assertEqual(plt.get_fignums(), [])


if __name__ == '__main__':
    unittest.main()
