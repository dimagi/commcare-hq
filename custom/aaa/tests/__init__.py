from __future__ import absolute_import, unicode_literals

import os
from datetime import date
from io import open

import mock
import postgres_copy
import six
import sqlalchemy
from django.test.utils import override_settings

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager
from custom.aaa.tasks import (
    update_child_table,
    update_woman_table,
    update_ccs_record_table,
    update_agg_awc_table,
    update_agg_village_table,
)


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
INPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'ucr_tables')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'agg_tables')
TEST_DOMAIN = 'reach-test'
TEST_ENVIRONMENT = 'icds'


def setUpModule():
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


def tearDownModule():
    with override_settings(SERVER_ENVIRONMENT=TEST_ENVIRONMENT):
        configs = StaticDataSourceConfiguration.by_domain(TEST_DOMAIN)
        adapters = [get_indicator_adapter(config) for config in configs]
        for adapter in adapters:
            adapter.drop_table()
