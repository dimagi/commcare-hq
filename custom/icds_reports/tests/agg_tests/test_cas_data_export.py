import csv
import io
import os

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.queries import get_cas_data_blob_file
from custom.icds_reports.tests.agg_tests import CSVTestCase, OUTPUT_PATH
from custom.icds_reports.utils import filter_cas_data_export


class TestCasDataExport(CSVTestCase):
    def _get_data_from_blobdb(self, indicator, state_id, month):
        sync, _ = get_cas_data_blob_file(indicator, state_id, month)
        with sync.get_file_from_blobdb() as fileobj:
            csv_file = io.TextIOWrapper(fileobj, encoding='utf-8')
            csv_data = list(csv.reader(csv_file))
        rows = self._transform_data_to_dict(csv_data)
        return rows

    def _transform_data_to_dict(self, csv_data):
        headers = csv_data[0]
        rows = csv_data[1:]
        for row_count, row in enumerate(rows):
            rows[row_count] = dict(zip(headers, row))
        return rows


class TestBeneficiaryDataExport(TestCasDataExport):
    always_include_columns = {'awc_id', 'case_id'}

    def test_child_health_monthly_cas_data(self):
        indicator = 'child_health_monthly'
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
        indicator = 'ccs_record_monthly'
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


class TestAwcExport(TestCasDataExport):
    always_include_columns = {'awc_id'}

    def test_agg_awc_cas_data(self):
        indicator = 'agg_awc'
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


class TestFilteredExport(TestCasDataExport):
    always_include_columns = {'awc_id'}

    def test_filtered_cas_data_export(self):
        indicator = 'agg_awc'
        state_id = 'st1'
        month = '2017-05-01'
        full_data, _ = get_cas_data_blob_file(indicator, state_id, month)
        block = SQLLocation.objects.get(name='b1')
        filtered_csv = filter_cas_data_export(full_data, block)
        with open(filtered_csv, 'r') as f:
            filtered_data = list(csv.reader(f))
        expected_csv_file = self._load_csv(
            os.path.join(OUTPUT_PATH, 'agg_awc-st1-2017-05-01_filtered.csv')
        )
        self._fasterAssertListEqual(
            sorted(
                expected_csv_file,
                key=lambda x: x['awc_id']
            ),
            sorted(
                self._transform_data_to_dict(filtered_data),
                key=lambda x: x['awc_id']
            )
        )
