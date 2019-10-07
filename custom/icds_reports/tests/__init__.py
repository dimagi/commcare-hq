import os
from datetime import datetime

import mock
import sqlalchemy
import csv

from django.conf import settings
from django.test.utils import override_settings
from django.test.testcases import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager, ICDS_UCR_CITUS_ENGINE_ID

from custom.icds_reports.tasks import (
    move_ucr_data_into_aggregation_tables,
    build_incentive_report,
)
from .agg_setup import setup_location_hierarchy, setup_tables_and_fixtures, aggregate_state_form_data

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'outputs')


def setUpModule():
    if settings.USE_PARTITIONED_DATABASE:
        print('============= WARNING: not running test setup because settings.USE_PARTITIONED_DATABASE is True.')
        return

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()

    domain = create_domain('icds-cas')
    setup_location_hierarchy(domain.name)

    with override_settings(SERVER_ENVIRONMENT='icds'):
        setup_tables_and_fixtures(domain.name)
        aggregate_state_form_data()
        try:
            with mock.patch('custom.icds_reports.tasks._update_aggregate_locations_tables'):
                move_ucr_data_into_aggregation_tables(datetime(2017, 5, 28), intervals=2)
            build_incentive_report(agg_date=datetime(2017, 5, 28))
        except Exception as e:
            print(e)
            tearDownModule()
            raise
        finally:
            _call_center_domain_mock.stop()


def tearDownModule():
    if settings.USE_PARTITIONED_DATABASE:
        return

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()
    with override_settings(SERVER_ENVIRONMENT='icds'):
        configs = StaticDataSourceConfiguration.by_domain('icds-cas')
        adapters = [get_indicator_adapter(config) for config in configs]
        for adapter in adapters:
            if adapter.config.table_id == 'static-child_health_cases':
                # hack because this is in a migration
                adapter.clear_table()
                continue
            adapter.drop_table()

        engine = connection_manager.get_engine(ICDS_UCR_CITUS_ENGINE_ID)
        with engine.begin() as connection:
            metadata = sqlalchemy.MetaData(bind=engine)
            metadata.reflect(bind=engine, extend_existing=True)
            for name in ('ucr_table_name_mapping', 'awc_location', 'awc_location_local'):
                table = metadata.tables[name]
                delete = table.delete()
                connection.execute(delete)
    LocationType.objects.filter(domain='icds-cas').delete()
    SQLLocation.objects.filter(domain='icds-cas').delete()

    Domain.get_by_name('icds-cas').delete()
    _call_center_domain_mock.stop()


class CSVTestCase(TestCase):

    def _load_csv(self, path):
        with open(path, encoding='utf-8') as f:
            csv_data = list(csv.reader(f))
            headers = csv_data[0]
            for row_count, row in enumerate(csv_data):
                csv_data[row_count] = dict(zip(headers, row))
        return csv_data[1:]

    def _fasterAssertListEqual(self, list1, list2):
        if len(list1) != len(list2):
            self.fail(f'Unequal number of entries: list1 {len(list1)}, list2 {len(list2)}')

        messages = []

        for idx in range(len(list1)):
            dict1 = list1[idx]
            dict2 = list2[idx]

            differences = set()

            for key in dict1.keys():
                if key != 'id':
                    if isinstance(dict1[key], str):
                        value1 = dict1[key]
                    elif isinstance(dict1[key], list):
                        value1 = str(dict1[key])
                    else:
                        value1 = dict1[key].decode('utf-8')
                    value1 = value1.replace('\r\n', '\n')
                    value2 = dict2.get(key, '').replace('\r\n', '\n')
                    if value1 != value2:
                        differences.add(key)

            if differences:
                if self.always_include_columns:
                    differences |= self.always_include_columns
                messages.append("""
                    Actual and expected row {} are not the same
                    Actual:   {}
                    Expected: {}
                """.format(
                    idx + 1,
                    ', '.join(['{}: {}'.format(
                        difference, str(dict1[difference])) for difference in differences]
                    ),
                    ', '.join(['{}: {}'.format(
                        difference, dict2.get(difference, '')) for difference in differences]
                    )
                ))

        if messages:
            self.fail('\n'.join(messages))
