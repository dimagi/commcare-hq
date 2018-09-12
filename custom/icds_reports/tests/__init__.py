from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
from datetime import datetime

import mock
import postgres_copy
import sqlalchemy

from django.conf import settings
from django.db import connections
from django.test.utils import override_settings

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from custom.icds_reports.tasks import (
    create_views,
    move_ucr_data_into_aggregation_tables,
    _aggregate_child_health_pnc_forms,
    _aggregate_gm_forms)
from io import open

FILE_NAME_TO_TABLE_MAPPING = {
    'awc_mgmt': 'config_report_icds-cas_static-awc_mgt_forms_ad1b11f0',
    'ccs_monthly': 'config_report_icds-cas_static-ccs_record_cases_monthly_d0e2e49e',
    'child_cases': 'config_report_icds-cas_static-child_health_cases_a46c129f',
    'child_monthly': 'config_report_icds-cas_static-child_cases_monthly_tabl_551fd064',
    'daily_feeding': 'config_report_icds-cas_static-daily_feeding_forms_85b1167f',
    'household_cases': 'config_report_icds-cas_static-household_cases_eadc276d',
    'infrastructure': 'config_report_icds-cas_static-infrastructure_form_05fe0f1a',
    'infrastructure_v2': 'config_report_icds-cas_static-infrastructure_form_v2_36e9ebb0',
    'location_ucr': 'config_report_icds-cas_static-awc_location_88b3f9c3',
    'person_cases': 'config_report_icds-cas_static-person_cases_v2_b4b5d57a',
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
}


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
                    postgres_copy.copy_from(f, table, engine, format=b'csv', null=b'', header=True)

        _aggregate_child_health_pnc_forms('st1', datetime(2017, 3, 31))
        _aggregate_gm_forms('st1', datetime(2017, 3, 31))

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

        with connections['icds-ucr'].cursor() as cursor:
            create_views(cursor)


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
