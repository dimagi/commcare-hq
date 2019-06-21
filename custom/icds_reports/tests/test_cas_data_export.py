from __future__ import absolute_import

from __future__ import unicode_literals

from custom.icds_reports.queries import get_cas_data_blob_file

import io
import os
import csv342 as csv

from custom.icds_reports.tests import OUTPUT_PATH, CSVTestCase
from six.moves import zip


class TestLocationView(CSVTestCase):
    always_include_columns = {'awc_id', 'case_id'}
    # indicator numbers:
    # 1 - child_health_monthly
    # 2 - ccs_record_monthly
    # 3 - agg_awc

    def _get_data_from_blobdb(self, indicator, state_id, month):
        sync, _ = get_cas_data_blob_file(indicator, state_id, month)
        with sync.get_file_from_blobdb() as fileobj:
            csv_file = io.TextIOWrapper(fileobj, encoding='utf-8')
            csv_data = list(csv.reader(csv_file))
        headers = csv_data[0]
        rows = csv_data[1:]
        for row_count, row in enumerate(rows):
            rows[row_count] = dict(zip(headers, row))
        return rows

    def test_child_health_monthly_cas_data(self):
        indicator = 1
        state_id = 'st1'
        month = '2017-05-01'
        csv_data = self._get_data_from_blobdb(indicator, state_id, month)
        expected_csv_file = self._load_csv(
            os.path.join(OUTPUT_PATH, 'child_health_monthly-st1-2017-05-01.csv')
        )
        self._fasterAssertListEqual(
            sorted(
                expected_csv_file,
                key=lambda x: x['case_id']
            ),
            sorted(
                csv_data,
                key=lambda x: x['case_id']
            )
        )

    def test_ccs_record_monthly_cas_data(self):
        indicator = 2
        state_id = 'st1'
        month = '2017-05-01'
        csv_data = self._get_data_from_blobdb(indicator, state_id, month)
        expected_csv_file = self._load_csv(
            os.path.join(OUTPUT_PATH, 'ccs_record_monthly-st1-2017-05-01.csv')
        )
        self._fasterAssertListEqual(
            sorted(
                csv_data,
                key=lambda x: x['case_id']
            ),
            sorted(
                expected_csv_file,
                key=lambda x: x['case_id']
            ),
        )

    def test_agg_awc_cas_data(self):
        indicator = 3
        state_id = 'st1'
        month = '2017-05-01'
        csv_data = self._get_data_from_blobdb(indicator, state_id, month)
        expected_csv_file = self._load_csv(
            os.path.join(OUTPUT_PATH, 'agg_awc-st1-2017-05-01.csv')
        )
        self._fasterAssertListEqual(
            sorted(
                expected_csv_file,
                key=lambda x: x['awc_id']
            ),
            sorted(
                csv_data,
                key=lambda x: x['awc_id']
            )
        )
