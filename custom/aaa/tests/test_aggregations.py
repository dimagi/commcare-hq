from __future__ import absolute_import, unicode_literals

import os
import re
from datetime import date, time
from decimal import Decimal
from io import open

from django.test.utils import override_settings

import mock
import postgres_copy
import six
import sqlalchemy
from six.moves import range

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import connection_manager
from custom.aaa.models import (
    AggAwc,
    AggVillage,
    CcsRecord,
    Child,
    Woman,
)
from custom.aaa.tasks import run_aggregation
from custom.icds_reports.tests import CSVTestCase

FILE_NAME_TO_TABLE_MAPPING = {
    'ccs_record': get_table_name('reach-test', 'reach-ccs_record_cases'),
    'child_health': get_table_name('reach-test', 'reach-child_health_cases'),
    'eligible_couple_forms': get_table_name('reach-test', 'reach-eligible_couple_forms'),
    'growth_monitoring': get_table_name('reach-test', 'reach-growth_monitoring_forms'),
    'household': get_table_name('reach-test', 'reach-household_cases'),
    'person': get_table_name('reach-test', 'reach-person_cases'),
    'tasks': get_table_name('reach-test', 'reach-tasks_cases'),
}
INPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'ucr_tables')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'agg_tables')
TEST_DOMAIN = 'reach-test'
TEST_ENVIRONMENT = 'icds'


@override_settings(SERVER_ENVIRONMENT='icds')
class AggregationScriptTestBase(CSVTestCase):
    always_include_columns = {'person_case_id'}
    fixtures = ['locations.json']

    @classmethod
    def setUpClass(cls):
        super(AggregationScriptTestBase, cls).setUpClass()
        _setup_ucr_tables()

        for month in range(1, 3):
            run_aggregation(TEST_DOMAIN, date(2019, month, 1))

    @classmethod
    def tearDownClass(cls):
        for model in (AggAwc, AggVillage, Child, CcsRecord, Woman):
            model.objects.all().delete()
        super(AggregationScriptTestBase, cls).tearDownClass()
        # teardown after the django database tear down occurs to prevent database locks
        # UCR tables are managed through sqlalchemy and their teardown conflicted with django teardown locks
        _teardown_ucr_tables()

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

    def _load_data_from_db(self, table_cls, sort_key):
        for row in table_cls.objects.order_by(*sort_key).values().all():
            for key, value in list(row.items()):
                if isinstance(value, date):
                    row[key] = value.strftime('%Y-%m-%d')
                elif isinstance(value, time):
                    row[key] = value.strftime("%H:%M:%S.%f").rstrip('0').rstrip('.')
                elif isinstance(value, six.integer_types):
                    row[key] = str(value)
                elif isinstance(value, (float, Decimal)):
                    row[key] = self._convert_decimal_to_string(row[key])
                elif value is None:
                    row[key] = ''
            yield row

    def _load_and_compare_data(self, table_name, path, sort_key=None):
        self._fasterAssertListEqual(
            list(self._load_data_from_db(table_name, sort_key)),
            self._load_csv(path)
        )

    def test_agg_woman_table(self):
        self._load_and_compare_data(
            Woman,
            os.path.join(OUTPUT_PATH, 'woman.csv'),
            sort_key=['awc_id', 'village_id', 'person_case_id']
        )

    def test_agg_child_table(self):
        self._load_and_compare_data(
            Child,
            os.path.join(OUTPUT_PATH, 'child.csv'),
            sort_key=['awc_id', 'village_id', 'person_case_id']
        )

    def test_agg_ccs_record_table(self):
        self._load_and_compare_data(
            CcsRecord,
            os.path.join(OUTPUT_PATH, 'ccs_record.csv'),
            sort_key=['awc_id', 'village_id', 'ccs_record_case_id']
        )

    def test_agg_awc_table(self):
        self._load_and_compare_data(
            AggAwc,
            os.path.join(OUTPUT_PATH, 'agg_awc.csv'),
            sort_key=['month', 'state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        )

    def test_agg_village_table(self):
        self._load_and_compare_data(
            AggVillage,
            os.path.join(OUTPUT_PATH, 'agg_village.csv'),
            sort_key=['month', 'state_id', 'district_id', 'taluka_id', 'phc_id', 'sc_id', 'village_id']
        )


# The following setup and teardown methods are kept here to allow quick loading of test data
# outside of the test suite
def _setup_ucr_tables():
    with mock.patch('corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'):
        with override_settings(SERVER_ENVIRONMENT=TEST_ENVIRONMENT):
            configs = StaticDataSourceConfiguration.by_domain(TEST_DOMAIN)
            adapters = [get_indicator_adapter(config) for config in configs]

            for adapter in adapters:
                try:
                    adapter.drop_table()
                except Exception:
                    pass
                adapter.build_table()

    engine = connection_manager.get_engine('aaa-data')
    metadata = sqlalchemy.MetaData(bind=engine)
    metadata.reflect(bind=engine, extend_existing=True)

    for file_name in os.listdir(INPUT_PATH):
        with open(os.path.join(INPUT_PATH, file_name), encoding='utf-8') as f:
            table_name = FILE_NAME_TO_TABLE_MAPPING[file_name[:-4]]
            table = metadata.tables[table_name]
            columns = [
                '"{}"'.format(c.strip())  # quote to preserve case
                for c in f.readline().split(',')
            ]
            postgres_copy.copy_from(
                f, table, engine, format='csv' if six.PY3 else b'csv',
                null='' if six.PY3 else b'', columns=columns
            )


def _teardown_ucr_tables():
    with override_settings(SERVER_ENVIRONMENT=TEST_ENVIRONMENT):
        configs = StaticDataSourceConfiguration.by_domain(TEST_DOMAIN)
        adapters = [get_indicator_adapter(config) for config in configs]
        for adapter in adapters:
            adapter.drop_table()
