from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
from datetime import datetime

import mock
import postgres_copy
import six
import sqlalchemy
import csv342 as csv

from django.conf import settings
from django.test.utils import override_settings
from django.test.testcases import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from custom.icds_reports.tasks import (
    move_ucr_data_into_aggregation_tables,
    _aggregate_child_health_pnc_forms,
    _aggregate_bp_forms,
    _aggregate_gm_forms)
from io import open
from six.moves import range
from six.moves import zip

FILE_NAME_TO_TABLE_MAPPING = {
    'awc_mgmt': 'config_report_icds-cas_static-awc_mgt_forms_ad1b11f0',
    'ccs_monthly': 'config_report_icds-cas_static-ccs_record_cases_monthly_d0e2e49e',
    "ccs_cases": "config_report_icds-cas_static-ccs_record_cases_cedcca39",
    'child_cases': 'config_report_icds-cas_static-child_health_cases_a46c129f',
    'daily_feeding': 'config_report_icds-cas_static-daily_feeding_forms_85b1167f',
    'household_cases': 'config_report_icds-cas_static-household_cases_eadc276d',
    'infrastructure': 'config_report_icds-cas_static-infrastructure_form_05fe0f1a',
    'infrastructure_v2': 'config_report_icds-cas_static-infrastructure_form_v2_36e9ebb0',
    'location_ucr': 'config_report_icds-cas_static-awc_location_88b3f9c3',
    'person_cases': 'config_report_icds-cas_static-person_cases_v3_2ae0879a',
    'usage': 'config_report_icds-cas_static-usage_forms_92fbe2aa',
    'vhnd': 'config_report_icds-cas_static-vhnd_form_28e7fd58',
    'complementary_feeding': 'config_report_icds-cas_static-complementary_feeding_fo_4676987e',
    'aww_user': 'config_report_icds-cas_static-commcare_user_cases_85763310',
    'child_tasks': 'config_report_icds-cas_static-child_tasks_cases_3548e54b',
    'pregnant_tasks': 'config_report_icds-cas_static-pregnant-tasks_cases_6c2a698f',
    'thr_form': 'config_report_icds-cas_static-dashboard_thr_forms_b8bca6ea',
    'gm_form': 'config_report_icds-cas_static-dashboard_growth_monitor_8f61534c',
    'pnc_forms': 'config_report_icds-cas_static-postnatal_care_forms_0c30d94e',
    'dashboard_daily_feeding': 'config_report_icds-cas_dashboard_child_health_daily_fe_f83b12b7',
    'ls_awc_mgt': 'config_report_icds-cas_static-awc_mgt_forms_ad1b11f0',
    'ls_home_vists': 'config_report_icds-cas_static-ls_home_visit_forms_fill_53a43d79',
    'ls_vhnd': 'config_report_icds-cas_static-ls_vhnd_form_f2b97e26',
    'cbe_form': 'config_report_icds-cas_static-cbe_form_f7988a04',
    'agg_awc': 'agg_awc',
    'birth_preparedness': 'config_report_icds-cas_static-dashboard_birth_prepared_fd07c11f',
    'delivery_form': 'config_report_icds-cas_static-dashboard_delivery_forms_946d56bd',
}

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
    location_type = LocationType.objects.create(
        domain=domain.name,
        name='block',
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='b1',
        location_id='b1',
        location_type=location_type
    )

    state_location_type = LocationType.objects.create(
        domain=domain.name,
        name='state',
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st1',
        location_id='st1',
        location_type=state_location_type
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st2',
        location_id='st2',
        location_type=state_location_type
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st3',
        location_id='st3',
        location_type=state_location_type
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st4',
        location_id='st4',
        location_type=state_location_type
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st5',
        location_id='st5',
        location_type=state_location_type
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st6',
        location_id='st6',
        location_type=state_location_type
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='st7',
        location_id='st7',
        location_type=state_location_type
    )

    awc_location_type = LocationType.objects.create(
        domain=domain.name,
        name='awc',
    )
    SQLLocation.objects.create(
        domain=domain.name,
        name='a7',
        location_id='a7',
        location_type=awc_location_type
    )

    with override_settings(SERVER_ENVIRONMENT='icds-new'):
        configs = StaticDataSourceConfiguration.by_domain('icds-cas')
        adapters = [get_indicator_adapter(config) for config in configs]

        for adapter in adapters:
            try:
                adapter.drop_table()
            except Exception:
                pass
            adapter.build_table()

        engine = connection_manager.get_engine(ICDS_UCR_ENGINE_ID)
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect(bind=engine, extend_existing=True)
        path = os.path.join(os.path.dirname(__file__), 'fixtures')
        for file_name in os.listdir(path):
            with open(os.path.join(path, file_name), encoding='utf-8') as f:
                table_name = FILE_NAME_TO_TABLE_MAPPING[file_name[:-4]]
                table = metadata.tables[table_name]
                if not table_name.startswith('icds_dashboard_'):
                    columns = [
                        '"{}"'.format(c.strip())  # quote to preserve case
                        for c in f.readline().split(',')
                    ]
                    postgres_copy.copy_from(
                        f, table, engine, format='csv' if six.PY3 else b'csv',
                        null='' if six.PY3 else b'', columns=columns
                    )

        for state_id in ('st1', 'st2'):
            _aggregate_child_health_pnc_forms(state_id, datetime(2017, 3, 31))
            _aggregate_gm_forms(state_id, datetime(2017, 3, 31))
            _aggregate_bp_forms(state_id, datetime(2017, 3, 31))

        try:
            move_ucr_data_into_aggregation_tables(datetime(2017, 5, 28), intervals=2)
        except AssertionError as e:
            # we always use soft assert to email when the aggregation has completed
            if "Aggregation completed" not in str(e):
                print(e)
                tearDownModule()
                raise
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
    with override_settings(SERVER_ENVIRONMENT='icds-new'):
        configs = StaticDataSourceConfiguration.by_domain('icds-cas')
        adapters = [get_indicator_adapter(config) for config in configs]
        for adapter in adapters:
            if adapter.config.table_id == 'static-child_health_cases':
                # hack because this is in a migration
                adapter.clear_table()
                continue
            adapter.drop_table()

        engine = connection_manager.get_engine(ICDS_UCR_ENGINE_ID)
        with engine.begin() as connection:
            metadata = sqlalchemy.MetaData(bind=engine)
            metadata.reflect(bind=engine, extend_existing=True)
            table = metadata.tables['ucr_table_name_mapping']
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
            self.fail('Lists are not equal')

        messages = []

        for idx in range(len(list1)):
            dict1 = list1[idx]
            dict2 = list2[idx]

            differences = set()

            for key in dict1.keys():
                if key != 'id':
                    if isinstance(dict1[key], six.text_type):
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
