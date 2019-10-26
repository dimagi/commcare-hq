import os
import re
from datetime import date, datetime, time
from decimal import Decimal

from django.test.testcases import TestCase, override_settings

import sqlalchemy
from freezegun import freeze_time

from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import (
    ICDS_UCR_CITUS_ENGINE_ID,
    connection_manager,
)
from custom.icds_reports.models.aggregate import (
    AggregateInactiveAWW,
    AwcLocation,
    get_cursor,
    maybe_atomic,
)
from custom.icds_reports.tasks import (
    _aggregate_ccs_record_thr_forms,
    _aggregate_bp_forms,
    _aggregate_ccs_record_pnc_forms,
    _aggregate_ccs_cf_forms,
    _aggregate_delivery_forms,
    _ccs_record_monthly_table,
    _get_monthly_dates,
)
from custom.icds_reports.tests.agg_tests import OUTPUT_PATH, CSVTestCase
from custom.icds_reports.tests.agg_tests.agg_setup import (
    distribute_tables_for_citus,
    setup_table_from_fixture,

)
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
    fixtures_needed = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        configs = StaticDataSourceConfiguration.by_domain('icds-cas')
        adapters = [get_indicator_adapter(config) for config in configs]

        for adapter in adapters:
            try:
                adapter.drop_table()
            except Exception:
                pass
            adapter.build_table()

        for file_name in cls.fixtures_needed:
            setup_table_from_fixture(file_name)
        engine = connection_manager.get_engine(ICDS_UCR_CITUS_ENGINE_ID)
        distribute_tables_for_citus(engine)

    @classmethod
    def tearDownClass(cls):
        engine = connection_manager.get_engine(ICDS_UCR_CITUS_ENGINE_ID)
        with engine.begin() as connection:
            metadata = sqlalchemy.MetaData(bind=engine)
            metadata.reflect(bind=engine, extend_existing=True)
            for name in ('ucr_table_name_mapping', 'awc_location', 'awc_location_local'):
                table = metadata.tables[name]
                delete = table.delete()
                connection.execute(delete)
        configs = StaticDataSourceConfiguration.by_domain('icds-cas')
        adapters = [get_indicator_adapter(config) for config in configs]

        for adapter in adapters:
            try:
                adapter.drop_table()
            except Exception:
                pass
        super().tearDownClass()

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


class CcsRecordMonthlyAggregationTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id', 'case_id'}
    fixtures_needed = [
        'ccs_cases.csv',
        'pregnant_tasks.csv',
        'person_cases.csv',
        'thr_form.csv',
        'birth_preparedness.csv',
        'pnc_forms.csv',
        'complementary_feeding.csv',
        'delivery_form.csv',
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        for state_id in ('st1', 'st2'):
            _aggregate_bp_forms(state_id, datetime(2017, 3, 31))

        for month in _get_monthly_dates(date(2017, 5, 28), 2):
            for state_id in ('st1', 'st2'):
                _aggregate_ccs_record_thr_forms(state_id, month)
                _aggregate_bp_forms(state_id, month)
                _aggregate_ccs_record_pnc_forms(state_id, month)
                _aggregate_ccs_cf_forms(state_id, month)
                _aggregate_delivery_forms(state_id, month)
            _ccs_record_monthly_table(month)

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
