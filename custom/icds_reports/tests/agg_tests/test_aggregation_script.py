import os
import re
from datetime import date, datetime, time
from decimal import Decimal

from django.test.testcases import TestCase, override_settings

import sqlalchemy
from freezegun import freeze_time

from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.sql_db.connections import (
    ICDS_UCR_CITUS_ENGINE_ID,
    connection_manager,
)
from custom.icds_reports.models.aggregate import (
    AggregateInactiveAWW,
    AwcLocation,
    get_cursor,
    maybe_atomic
)
from custom.icds_reports.tests.agg_tests import OUTPUT_PATH, CSVTestCase
from custom.icds_reports.utils.aggregation_helpers.distributed import (
    InactiveAwwsAggregationDistributedHelper,
    LocationAggregationDistributedHelper,
)


@override_settings(SERVER_ENVIRONMENT='icds')
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
        session_helper = connection_manager.get_session_helper(ICDS_UCR_CITUS_ENGINE_ID)
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
                    elif isinstance(value, int):
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
        'aggregation_level',
        'state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id',
        'gender', 'age_tranche', 'caste', 'disabled', 'minority', 'resident',
    )
    always_include_columns = set(sort_key)

    def test_agg_child_health_2017_04_01(self):
        self._load_and_compare_data(
            'agg_child_health_2017-04-01',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-04-01_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-04-01'}
        )

    def test_agg_child_health_2017_05_01(self):
        self._load_and_compare_data(
            'agg_child_health_2017-05-01',
            os.path.join(OUTPUT_PATH, 'agg_child_health_2017-05-01_sorted.csv'),
            sort_key=self.sort_key,
            filter_by={'month': '2017-05-01'}
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


@override_settings(SERVER_ENVIRONMENT='icds')
class InactiveAWWsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(InactiveAWWsTest, cls).setUpClass()
        last_sync = date(2017, 4, 1)
        cls.agg_time = datetime(2017, 7, 31, 18)
        cls.helper = InactiveAwwsAggregationDistributedHelper(last_sync)

    def tearDown(self):
        AggregateInactiveAWW.objects.all().delete()

    def test_missing_locations_query(self):
        with freeze_time(self.agg_time):
            missing_location_query = self.helper.missing_location_query()
        with get_cursor(AggregateInactiveAWW) as cursor:
            cursor.execute(missing_location_query)
        records = AggregateInactiveAWW.objects.filter(first_submission__isnull=False)
        self.assertEqual(records.count(), 0)

    def test_aggregate_query(self):
        with freeze_time(self.agg_time):
            missing_location_query = self.helper.missing_location_query()
            aggregation_query, agg_params = self.helper.aggregate_query()
        with get_cursor(AggregateInactiveAWW) as cursor:
            cursor.execute(missing_location_query)
            cursor.execute(aggregation_query, agg_params)
        records = AggregateInactiveAWW.objects.filter(first_submission__isnull=False)
        self.assertEqual(records.count(), 46)

    def test_submission_dates(self):
        with freeze_time(self.agg_time):
            missing_location_query = self.helper.missing_location_query()
            aggregation_query, agg_params = self.helper.aggregate_query()
        with get_cursor(AggregateInactiveAWW) as cursor:
            cursor.execute(missing_location_query)
            cursor.execute(aggregation_query, agg_params)
        record = AggregateInactiveAWW.objects.filter(awc_id='a10').first()
        self.assertEqual(date(2017, 4, 5), record.first_submission)
        self.assertEqual(date(2017, 5, 5), record.last_submission)


@override_settings(SERVER_ENVIRONMENT='icds')
class LocationAggregationTest(TestCase):
    domain_name = 'icds-cas'

    @classmethod
    def setUpClass(cls):
        super(LocationAggregationTest, cls).setUpClass()

        # save locations that are setup in module so we can add them back later
        cls.all_locations = list(SQLLocation.objects.filter(domain=cls.domain_name).all())
        cls.all_location_types = list(LocationType.objects.filter(domain=cls.domain_name).all())
        SQLLocation.objects.filter(domain=cls.domain_name).delete()
        LocationType.objects.filter(domain=cls.domain_name).delete()

        setup_locations_and_types(
            cls.domain_name,
            ['state', 'district', 'block', 'supervisor', 'awc'],
            [],
            [
                ('State1', [
                    ('District1', [
                        ('Block1', [
                            ('Supervisor1', [
                                ('Awc1', []),
                                ('Awc2', []),
                            ]),
                            ('Supervisor2', [
                                ('Awc3', []),
                            ]),
                        ]),
                        ('Block2', []),
                    ]),
                ])
            ]
        )

        block1 = SQLLocation.objects.filter(domain=cls.domain_name, name='Block1').first()
        block1.metadata = {"map_location_name": "Not Block1"}
        block1.save()

        sup2 = SQLLocation.objects.filter(domain=cls.domain_name, name='Supervisor2').first()
        sup2.metadata = {"is_test_location": "test"}
        sup2.save()

        awc1 = SQLLocation.objects.filter(domain=cls.domain_name, name='Awc1').first()
        awc1.location_id = 'a1'
        awc1.save()
        cls.helper = LocationAggregationDistributedHelper()

    @classmethod
    def tearDownClass(cls):
        SQLLocation.objects.filter(domain=cls.domain_name).delete()
        LocationType.objects.filter(domain=cls.domain_name).delete()
        LocationType.objects.bulk_create(cls.all_location_types)
        SQLLocation.objects.bulk_create(cls.all_locations)
        super(LocationAggregationTest, cls).tearDownClass()

    def test_number_rows_csv(self):
        csv = self.helper.generate_csv()
        self.assertEqual(len(csv.readlines()), 4)

    def test_agg(self):
        # This is copied over in the module
        self.assertEqual(AwcLocation.objects.count(), 92)
        self.maxDiff = None

        with maybe_atomic(AwcLocation):
            try:
                with maybe_atomic(AwcLocation):
                    # run agg again without any locations in awc_location
                    with get_cursor(AwcLocation) as cursor:
                        cursor.execute("DELETE FROM awc_location")
                        cursor.execute("DELETE FROM awc_location_local")
                        self.helper.aggregate(cursor)

                    self.assertEqual(AwcLocation.objects.count(), 8)
                    self.assertEqual(
                        list(AwcLocation.objects.values(
                            'aggregation_level',
                            'awc_is_test', 'awc_name', 'awc_site_code',
                            'supervisor_is_test', 'supervisor_name', 'supervisor_site_code',
                            'block_is_test', 'block_name', 'block_site_code', 'block_map_location_name',
                            'district_is_test', 'district_name', 'district_site_code', 'district_map_location_name',
                            'state_is_test', 'state_name', 'state_site_code', 'state_map_location_name',
                            'awc_ward_1', 'awc_ward_2', 'awc_ward_3'
                        ).order_by(
                            '-aggregation_level', 'awc_name', 'supervisor_name',
                            'block_name', 'district_name', 'state_name'
                        ).all()),
                        self._expected_end_state
                    )
                    raise Exception("Don't allow this to be commited")
            except Exception as e:
                if 'allow this' not in str(e):
                    raise

    @property
    def _expected_end_state(self):
        return [
            {
                'aggregation_level': 5,
                'awc_is_test': 0, 'awc_name': 'Awc1', 'awc_site_code': 'awc1',
                'supervisor_is_test': 0, 'supervisor_name': 'Supervisor1', 'supervisor_site_code': 'supervisor1',
                'block_is_test': 0, 'block_map_location_name': 'Not Block1',
                'block_name': 'Block1', 'block_site_code': 'block1',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': 'ward_1',
                'awc_ward_2': 'ward_2',
                'awc_ward_3': 'ward_3',
            },
            {
                'aggregation_level': 5,
                'awc_is_test': 0, 'awc_name': 'Awc2', 'awc_site_code': 'awc2',
                'supervisor_is_test': 0, 'supervisor_name': 'Supervisor1', 'supervisor_site_code': 'supervisor1',
                'block_is_test': 0, 'block_map_location_name': 'Not Block1',
                'block_name': 'Block1', 'block_site_code': 'block1',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            },
            {
                'aggregation_level': 5,
                'awc_is_test': 0, 'awc_name': 'Awc3', 'awc_site_code': 'awc3',
                'supervisor_is_test': 1, 'supervisor_name': 'Supervisor2', 'supervisor_site_code': 'supervisor2',
                'block_is_test': 0, 'block_map_location_name': 'Not Block1',
                'block_name': 'Block1', 'block_site_code': 'block1',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            },
            {
                'aggregation_level': 4,
                'awc_is_test': 0, 'awc_name': None, 'awc_site_code': 'All',
                'supervisor_is_test': 0, 'supervisor_name': 'Supervisor1', 'supervisor_site_code': 'supervisor1',
                'block_is_test': 0, 'block_map_location_name': 'Not Block1',
                'block_name': 'Block1', 'block_site_code': 'block1',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            },
            {
                'aggregation_level': 4,
                'awc_is_test': 0, 'awc_name': None, 'awc_site_code': 'All',
                'supervisor_is_test': 1, 'supervisor_name': 'Supervisor2', 'supervisor_site_code': 'supervisor2',
                'block_is_test': 0, 'block_map_location_name': 'Not Block1',
                'block_name': 'Block1', 'block_site_code': 'block1',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            },
            {
                'aggregation_level': 3,
                'awc_is_test': 0, 'awc_name': None, 'awc_site_code': 'All',
                'supervisor_is_test': 0, 'supervisor_name': None, 'supervisor_site_code': 'All',
                'block_is_test': 0, 'block_map_location_name': 'Not Block1',
                'block_name': 'Block1', 'block_site_code': 'block1',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            },
            {
                'aggregation_level': 2,
                'awc_is_test': 0, 'awc_name': None, 'awc_site_code': 'All',
                'supervisor_is_test': 0, 'supervisor_name': None, 'supervisor_site_code': 'All',
                'block_is_test': 0, 'block_map_location_name': 'All',
                'block_name': None, 'block_site_code': 'All',
                'district_is_test': 0, 'district_map_location_name': None,
                'district_name': 'District1', 'district_site_code': 'district1',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            },
            {
                'aggregation_level': 1,
                'awc_is_test': 0, 'awc_name': None, 'awc_site_code': 'All',
                'supervisor_is_test': 0, 'supervisor_name': None, 'supervisor_site_code': 'All',
                'block_is_test': 0, 'block_map_location_name': 'All', 'block_name': None, 'block_site_code': 'All',
                'district_is_test': 0, 'district_map_location_name': 'All',
                'district_name': None, 'district_site_code': 'All',
                'state_is_test': 0, 'state_map_location_name': None,
                'state_name': 'State1', 'state_site_code': 'state1',
                'awc_ward_1': None,
                'awc_ward_2': None,
                'awc_ward_3': None,
            }
        ]
