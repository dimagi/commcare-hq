from __future__ import absolute_import, unicode_literals

import os
import re
from datetime import date, time
from decimal import Decimal
from io import open

import mock
import postgres_copy
import sqlalchemy
import six
from django.test.utils import override_settings

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager
from custom.aaa.models import (
    AggAwc,
    AggVillage,
    CcsRecord,
    Child,
    Woman,
)
from custom.aaa.tasks import (
    update_agg_awc_table,
    update_agg_village_table,
    update_ccs_record_table,
    update_child_table,
    update_woman_table,
)
from custom.icds_reports.tests import CSVTestCase

FILE_NAME_TO_TABLE_MAPPING = {
    'awc': 'config_report_reach-test_reach-awc_location_4646cfd7',
    'ccs_record': 'config_report_reach-test_reach-ccs_record_cases_eaef76c6',
    'child_health': 'config_report_reach-test_reach-child_health_cases_10a84c1d',
    'eligible_couple_forms': 'config_report_reach-test_reach-eligible_couple_forms_002d1d07',
    'growth_monitoring': 'config_report_reach-test_reach-growth_monitoring_forms_66bc5792',
    'household': 'config_report_reach-test_reach-household_cases_73b9e4e8',
    'person': 'config_report_reach-test_reach-person_cases_26a9647f',
    'village': 'config_report_reach-test_reach-village_location_569fb159',
}
# INPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'ucr_tables')
# OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'agg_tables')
TEST_DOMAIN = 'reach-test'
TEST_ENVIRONMENT = 'icds'


# @override_settings(SERVER_ENVIRONMENT='icds')
# class AggregationScriptTest(CSVTestCase):
#     always_include_columns = {'village_id'}
#
#     @classmethod
#     def setUpClass(cls):
#         super(AggregationScriptTest, cls).setUpClass()
#         _setup_ucr_tables()
#         update_child_table(TEST_DOMAIN)
#         update_woman_table(TEST_DOMAIN)
#         update_ccs_record_table(TEST_DOMAIN)
#
#         for month in range(1, 3):
#             update_agg_awc_table(TEST_DOMAIN, date(2019, month, 1))
#             update_agg_village_table(TEST_DOMAIN, date(2019, month, 1))
#
#     @classmethod
#     def tearDownClass(cls):
#         _teardown_ucr_tables()
#         super(AggregationScriptTest, cls).tearDownClass()
#
#     def _convert_decimal_to_string(self, value):
#         """
#             Args:
#                 value (decimal.Decimal)
#             Returns:
#                 str
#             Converts scientific notation to decimal form if needed.
#             it's needed because in csv file all numbers are written in decimal form.
#             Here is an example why we can't simply apply str to decimal number
#                 >>> str(Decimal('0.0000000'))
#                 '0E-7'
#                 >>> self._convert_decimal_to_string(Decimal('0.0000000'))
#                 '0.0000000'
#         """
#         value_str = str(value)
#         p = re.compile('0E-(?P<zeros>[0-9]+)')
#         match = p.match(value_str)
#         if match:
#             return '0.{}'.format(int(match.group('zeros')) * '0')
#         else:
#             return value_str
#
#     def _load_data_from_db(self, table_cls, sort_key):
#         for row in table_cls.objects.order_by(*sort_key).values().all():
#             for key, value in list(row.items()):
#                 if isinstance(value, date):
#                     row[key] = value.strftime('%Y-%m-%d')
#                 elif isinstance(value, time):
#                     row[key] = value.strftime("%H:%M:%S.%f").rstrip('0').rstrip('.')
#                 elif isinstance(value, six.integer_types):
#                     row[key] = str(value)
#                 elif isinstance(value, (float, Decimal)):
#                     row[key] = self._convert_decimal_to_string(row[key])
#                 elif isinstance(value, six.string_types):
#                     row[key] = value.encode('utf-8')
#                 elif value is None:
#                     row[key] = ''
#             yield row
#
#     def _load_and_compare_data(self, table_name, path, sort_key=None):
#         self._fasterAssertListEqual(
#             list(self._load_data_from_db(table_name, sort_key)),
#             self._load_csv(path)
#         )

    # def test_agg_woman_table(self):
    #     self._load_and_compare_data(
    #         Woman,
    #         os.path.join(OUTPUT_PATH, 'woman.csv'),
    #         sort_key=['awc_id', 'village_id', 'person_case_id']
    #     )

    # def test_agg_child_table(self):
    #     self._load_and_compare_data(
    #         Child,
    #         os.path.join(OUTPUT_PATH, 'child.csv'),
    #         sort_key=['awc_id', 'village_id', 'person_case_id']
    #     )
    #
    # def test_agg_ccs_record_table(self):
    #     self._load_and_compare_data(
    #         CcsRecord,
    #         os.path.join(OUTPUT_PATH, 'ccs_record.csv'),
    #         sort_key=['awc_id', 'village_id', 'ccs_record_case_id']
    #     )
    #
    # def test_agg_awc_table(self):
    #     self._load_and_compare_data(
    #         AggAwc,
    #         os.path.join(OUTPUT_PATH, 'agg_awc.csv'),
    #         sort_key=['month', 'state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
    #     )
    #
    # def test_agg_village_table(self):
    #     self._load_and_compare_data(
    #         AggVillage,
    #         os.path.join(OUTPUT_PATH, 'agg_village.csv'),
    #         sort_key=['month', 'state_id', 'district_id', 'taluka_id', 'phc_id', 'sc_id', 'village_id']
    #     )


# The following setup and teardown methods are kept here to allow quick loading of test data
# outside of the test suite
# def _setup_ucr_tables():
#     with mock.patch('corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'):
#         with override_settings(SERVER_ENVIRONMENT=TEST_ENVIRONMENT):
#             configs = StaticDataSourceConfiguration.by_domain(TEST_DOMAIN)
#             adapters = [get_indicator_adapter(config) for config in configs]
#
#             for adapter in adapters:
#                 try:
#                     adapter.drop_table()
#                 except Exception:
#                     pass
#                 adapter.build_table()
#
#     engine = connection_manager.get_engine('aaa-data')
#     metadata = sqlalchemy.MetaData(bind=engine)
#     metadata.reflect(bind=engine, extend_existing=True)
#
#     for file_name in os.listdir(INPUT_PATH):
#         with open(os.path.join(INPUT_PATH, file_name), encoding='utf-8') as f:
#             table_name = FILE_NAME_TO_TABLE_MAPPING[file_name[:-4]]
#             table = metadata.tables[table_name]
#             columns = [
#                 '"{}"'.format(c.strip())  # quote to preserve case
#                 for c in f.readline().split(',')
#             ]
#             postgres_copy.copy_from(
#                 f, table, engine, format='csv' if six.PY3 else b'csv',
#                 null='' if six.PY3 else b'', columns=columns
#             )

#
# def _teardown_ucr_tables():
#     with override_settings(SERVER_ENVIRONMENT=TEST_ENVIRONMENT):
#         configs = StaticDataSourceConfiguration.by_domain(TEST_DOMAIN)
#         adapters = [get_indicator_adapter(config) for config in configs]
#         for adapter in adapters:
#             adapter.drop_table()
