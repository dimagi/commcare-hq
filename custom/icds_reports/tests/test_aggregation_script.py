from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date, datetime, time
from decimal import Decimal
import os
import re

import six
import sqlalchemy

from django.test.testcases import TestCase, override_settings
from freezegun import freeze_time

from corehq.sql_db.connections import connection_manager
from six.moves import zip

from custom.icds_reports.models.aggregate import get_cursor, AggregateInactiveAWW
from custom.icds_reports.tests import CSVTestCase, OUTPUT_PATH
from custom.icds_reports.utils.aggregation_helpers.helpers import get_helper
from custom.icds_reports.utils.aggregation_helpers.monolith import InactiveAwwsAggregationHelper


@override_settings(SERVER_ENVIRONMENT='icds-new')
class AggregationScriptTestBase(CSVTestCase):
    """
    Note: test setup and teardown are done at module level using
        setUpModule and tearDownModule
    """

    always_include_columns = None

    def _convert_decimal_to_string(self, value):
        """
            Args:
                value (decimal.Decimal)
            Returns:
                str
            Converts scientific notation to decimal form if needed.
            it's needed because in csv file all numbers are written in decimal form.
            Here is an example why we can't simply apply str to decimal number
                >>> str(Decimal('0.0000000'))
                '0E-7'
                >>> self._convert_decimal_to_string(Decimal('0.0000000'))
                '0.0000000'
        """
        value_str = str(value)
        p = re.compile('0E-(?P<zeros>[0-9]+)')
        match = p.match(value_str)
        if match:
            return '0.{}'.format(int(match.group('zeros')) * '0')
        else:
            return value_str

    def _load_data_from_db(self, table_name, sort_key, filter_by=None):
        session_helper = connection_manager.get_session_helper('icds-ucr')
        engine = session_helper.engine
        session = session_helper.Session
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect(bind=engine)
        table = metadata.tables[table_name]
        columns = [
            column.name
            for column in table.columns
        ]
        with engine.begin() as connection:
            query = session.query(table).order_by(*sort_key)
            if filter_by:
                query = query.filter_by(**filter_by)
            rows = query.all()
            for row in rows:
                row = list(row)
                for idx, value in enumerate(row):
                    if isinstance(value, date):
                        row[idx] = value.strftime('%Y-%m-%d')
                    elif isinstance(value, time):
                        row[idx] = value.strftime("%H:%M:%S.%f").rstrip('0').rstrip('.')
                    elif isinstance(value, six.integer_types):
                        row[idx] = str(value)
                    elif isinstance(value, (float, Decimal)):
                        row[idx] = self._convert_decimal_to_string(row[idx])
                    elif value is None:
                        row[idx] = ''
                yield dict(zip(columns, row))

    def _load_and_compare_data(self, table_name, path, sort_key=None, filter_by=None):
        # To speed up tests, we use a sort_key wherever possible
        #   to presort before comparing data
        if sort_key:
            self._fasterAssertListEqual(
                list(self._load_data_from_db(table_name, sort_key, filter_by)),
                self._load_csv(path)
            )
        else:
            sort_key = lambda x: x
            self._fasterAssertListEqual(
                sorted(
                    list(self._load_data_from_db(table_name, [], filter_by)),
                    key=sort_key
                ),
                sorted(
                    self._load_csv(path),
                    key=sort_key
                )
            )


class AggregationScriptTest(AggregationScriptTestBase):
    def test_icds_months(self):
        self._load_and_compare_data(
            'icds_months',
            os.path.join(OUTPUT_PATH, 'icds_months_sorted.csv'),
            sort_key=['month_name']
        )


class CcsRecordMonthlyAggregationTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id', 'case_id'}

    def test_ccs_record_monthly_2017_04_01(self):
        self._load_and_compare_data(
            'ccs_record_monthly',
            os.path.join(OUTPUT_PATH, 'ccs_record_monthly_2017-04-01_sorted.csv'),
            sort_key=['awc_id', 'case_id'],
            filter_by={'month': '2017-04-01'}
        )

    def test_ccs_record_monthly_2017_05_01(self):
        self._load_and_compare_data(
            'ccs_record_monthly',
            os.path.join(OUTPUT_PATH, 'ccs_record_monthly_2017-05-01_sorted.csv'),
            sort_key=['awc_id', 'case_id'],
            filter_by={'month': '2017-05-01'}
        )


class CcsRecordAggregationTest(AggregationScriptTestBase):
    sort_key = (
        'state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id',
        'ccs_status', 'trimester', 'caste', 'disabled', 'minority', 'resident'
    )
    always_include_columns = set(sort_key)

    def test_agg_ccs_record_2017_04_01_1(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-04-01_1_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 1}
        )

    def test_agg_ccs_record_2017_04_01_2(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-04-01_2_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 2}
        )

    def test_agg_ccs_record_2017_04_01_3(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-04-01_3_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 3}
        )

    def test_agg_ccs_record_2017_04_01_4(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-04-01_4_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 4}
        )

    def test_agg_ccs_record_2017_04_01_5(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-04-01_5_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 5}
        )

    def test_agg_ccs_record_2017_05_01_1(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-05-01_1_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 1}
        )

    def test_agg_ccs_record_2017_05_01_2(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-05-01_2_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 2}
        )

    def test_agg_ccs_record_2017_05_01_3(self):
        self._load_and_compare_data(
            'agg_ccs_record_2017-05-01_3',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-05-01_3_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 3}
        )

    def test_agg_ccs_record_2017_05_01_4(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-05-01_4_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 4}
        )

    def test_agg_ccs_record_2017_05_01_5(self):
        self._load_and_compare_data(
            'agg_ccs_record',
            os.path.join(OUTPUT_PATH, 'agg_ccs_record_2017-05-01_5_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 5}
        )


class AggChildHealthAggregationTest(AggregationScriptTestBase):
    sort_key = (
        'state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id',
        'gender', 'age_tranche', 'caste', 'disabled', 'minority', 'resident',
    )
    always_include_columns = set(sort_key)

    def test_agg_child_health_2017_04_01_1(self):
        self._load_and_compare_data(
            'agg_child_health_2017-04-01_1',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-04-01_1_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 1}
        )

    def test_agg_child_health_2017_04_01_2(self):
        self._load_and_compare_data(
            'agg_child_health_2017-04-01_2',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-04-01_2_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 2}
        )

    def test_agg_child_health_2017_04_01_3(self):
        self._load_and_compare_data(
            'agg_child_health_2017-04-01_3',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-04-01_3_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 3}
        )

    def test_agg_child_health_2017_04_01_4(self):
        self._load_and_compare_data(
            'agg_child_health_2017-04-01_4',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-04-01_4_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 4}
        )

    def test_agg_child_health_2017_04_01_5(self):
        self._load_and_compare_data(
            'agg_child_health_2017-04-01_5',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-04-01_5_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01', 'aggregation_level': 5}
        )

    def test_agg_child_health_2017_05_01_1(self):
        self._load_and_compare_data(
            'agg_child_health_2017-05-01_1',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-05-01_1_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 1}
        )
    def test_agg_child_health_2017_05_01_2(self):
        self._load_and_compare_data(
            'agg_child_health_2017-05-01_2',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-05-01_2_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 2}
        )

    def test_agg_child_health_2017_05_01_3(self):
        self._load_and_compare_data(
            'agg_child_health_2017-05-01_3',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-05-01_3_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 3}
        )

    def test_agg_child_health_2017_05_01_4(self):
        self._load_and_compare_data(
            'agg_child_health_2017-05-01_4',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-05-01_4_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 4}
        )

    def test_agg_child_health_2017_05_01_5(self):
        self._load_and_compare_data(
            'agg_child_health_2017-05-01_5',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-05-01_5_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01', 'aggregation_level': 5}
        )


class AggLsAggregationTest(AggregationScriptTestBase):
    always_include_columns = {'state_id', 'district_id', 'block_id', 'supervisor_id'}

    def test_agg_ls_2017_05_01_4(self):
        self._load_and_compare_data(
            'agg_ls_2017-05-01_4',
            os.path.join(OUTPUT_PATH, 'agg_ls_2017-05-01_4_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id']
        )

    def test_agg_ls_2017_05_01_3(self):
        self._load_and_compare_data(
            'agg_ls_2017-05-01_3',
            os.path.join(OUTPUT_PATH, 'agg_ls_2017-05-01_3_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id']
        )

    def test_agg_ls_2017_05_01_2(self):
        self._load_and_compare_data(
            'agg_ls_2017-05-01_2',
            os.path.join(OUTPUT_PATH, 'agg_ls_2017-05-01_2_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id']
        )

    def test_agg_ls_2017_05_01_1(self):
        self._load_and_compare_data(
            'agg_ls_2017-05-01_1',
            os.path.join(OUTPUT_PATH, 'agg_ls_2017-05-01_1_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id']
        )


class AggAwcAggregationTest(AggregationScriptTestBase):
    always_include_columns = {'state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id'}

    def test_agg_awc_daily(self):
        self._load_and_compare_data(
            'agg_awc_daily_2017-05-28',
            os.path.join(OUTPUT_PATH, 'agg_awc_daily_2017-05-28_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_04_01_1(self):
        self._load_and_compare_data(
            'agg_awc_2017-04-01_1',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-04-01_1_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_04_01_2(self):
        self._load_and_compare_data(
            'agg_awc_2017-04-01_2',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-04-01_2_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_04_01_3(self):
        self._load_and_compare_data(
            'agg_awc_2017-04-01_3',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-04-01_3_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_04_01_4(self):
        self._load_and_compare_data(
            'agg_awc_2017-04-01_4',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-04-01_4_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_04_01_5(self):
        self._load_and_compare_data(
            'agg_awc_2017-04-01_5',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-04-01_5_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_05_01_1(self):
        self._load_and_compare_data(
            'agg_awc_2017-05-01_1',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-05-01_1_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_05_01_2(self):
        self._load_and_compare_data(
            'agg_awc_2017-05-01_2',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-05-01_2_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_05_01_3(self):
        self._load_and_compare_data(
            'agg_awc_2017-05-01_3',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-05-01_3_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_05_01_4(self):
        self._load_and_compare_data(
            'agg_awc_2017-05-01_4',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-05-01_4_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_awc_2017_05_01_5(self):
        self._load_and_compare_data(
            'agg_awc_2017-05-01_5',
            os.path.join(OUTPUT_PATH, 'agg_awc_2017-05-01_5_sorted.csv'),
            sort_key=['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )


class ChildHealthMonthlyAggregationTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id', 'case_id'}

    def test_child_health_monthly_2017_04_01(self):
        self._load_and_compare_data(
            'child_health_monthly',
            os.path.join(OUTPUT_PATH, 'child_health_monthly_2017-04-01_sorted.csv'),
            sort_key=['awc_id', 'case_id'],
            filter_by={'month': '2017-04-01'}
        )

    def test_child_health_monthly_2017_05_01(self):
        self._load_and_compare_data(
            'child_health_monthly',
            os.path.join(OUTPUT_PATH, 'child_health_monthly_2017-05-01_sorted.csv'),
            sort_key=['awc_id', 'case_id'],
            filter_by={'month': '2017-05-01'}
        )


class DailyAttendanceAggregationTest(AggregationScriptTestBase):
    def test_daily_attendance_2017_04_01(self):
        self._load_and_compare_data(
            'daily_attendance',
            os.path.join(OUTPUT_PATH, 'daily_attendance_2017-04-01_sorted.csv'),
            sort_key=['awc_id', 'pse_date'],
            filter_by={'month': date(2017, 4, 1)}
        )

    def test_daily_attendance_2017_05_01(self):
        self._load_and_compare_data(
            'daily_attendance',
            os.path.join(OUTPUT_PATH, 'daily_attendance_2017-05-01_sorted.csv'),
            sort_key=['awc_id', 'pse_date'],
            filter_by={'month': date(2017, 5, 1)}
        )


@override_settings(SERVER_ENVIRONMENT='icds-new')
class InactiveAWWsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(InactiveAWWsTest, cls).setUpClass()
        last_sync = date(2017, 4, 1)
        cls.agg_time = datetime(2017, 5, 31, 18)
        helper_class = get_helper(InactiveAwwsAggregationHelper.helper_key)
        cls.helper = helper_class(last_sync)

    def tearDown(self):
        AggregateInactiveAWW.objects.all().delete()

    def test_missing_locations_query(self):
        missing_location_query = self.helper.missing_location_query()
        with freeze_time(self.agg_time), get_cursor(AggregateInactiveAWW) as cursor:
            cursor.execute(missing_location_query)
        records = AggregateInactiveAWW.objects.filter(first_submission__isnull=False)
        self.assertEquals(records.count(), 0)

    def test_aggregate_query(self):
        missing_location_query = self.helper.missing_location_query()
        aggregation_query, agg_params = self.helper.aggregate_query()
        with freeze_time(self.agg_time), get_cursor(AggregateInactiveAWW) as cursor:
            cursor.execute(missing_location_query)
            cursor.execute(aggregation_query, agg_params)
        records = AggregateInactiveAWW.objects.filter(first_submission__isnull=False)
        self.assertEquals(records.count(), 46)

    def test_submission_dates(self):
        missing_location_query = self.helper.missing_location_query()
        aggregation_query, agg_params = self.helper.aggregate_query()
        with freeze_time(self.agg_time), get_cursor(AggregateInactiveAWW) as cursor:
            cursor.execute(missing_location_query)
            cursor.execute(aggregation_query, agg_params)
        record = AggregateInactiveAWW.objects.filter(awc_id='a10').first()
        self.assertEquals(date(2017, 4, 5), record.first_submission)
        self.assertEquals(date(2017, 5, 5), record.last_submission)
