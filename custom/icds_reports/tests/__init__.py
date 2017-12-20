from __future__ import absolute_import
import os
from datetime import datetime

import mock
import postgres_copy
import sqlalchemy

from django.conf import settings
from django.test.utils import override_settings

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from custom.icds_reports.tasks import move_ucr_data_into_aggregation_tables

FILE_NAME_TO_TABLE_MAPPING = {
    'awc_mgmt': 'config_report_icds-cas_static-awc_mgt_forms_ad1b11f0',
    'ccs_cases': 'config_report_icds-cas_static-ccs_record_cases_cedcca39',
    'ccs_monthly': 'config_report_icds-cas_static-ccs_record_cases_monthly_d0e2e49e',
    'child_cases': 'config_report_icds-cas_static-child_health_cases_a46c129f',
    'child_monthly': 'config_report_icds-cas_static-child_cases_monthly_tabl_551fd064',
    'daily_feeding': 'config_report_icds-cas_static-daily_feeding_forms_85b1167f',
    'household_cases': 'config_report_icds-cas_static-household_cases_eadc276d',
    'infrastructure': 'config_report_icds-cas_static-infrastructure_form_05fe0f1a',
    'location_ucr': 'config_report_icds-cas_static-awc_location_88b3f9c3',
    'person_cases': 'config_report_icds-cas_static-person_cases_v2_b4b5d57a',
    'ucr_table_name_mapping': 'ucr_table_name_mapping',
    'usage': 'config_report_icds-cas_static-usage_forms_92fbe2aa',
    'vhnd': 'config_report_icds-cas_static-vhnd_form_28e7fd58'
}


def setUpModule():
    if settings.USE_PARTITIONED_DATABASE:
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

    with override_settings(SERVER_ENVIRONMENT='icds'):
        configs = StaticDataSourceConfiguration.by_domain('icds-cas')
        adapters = [get_indicator_adapter(config) for config in configs]

        for adapter in adapters:
            if adapter.config.table_id == 'static-child_health_cases':
                # hack because this is in a migration
                continue
            adapter.build_table()

        engine = connection_manager.get_engine(ICDS_UCR_ENGINE_ID)
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect(bind=engine, extend_existing=True)
        path = os.path.join(os.path.dirname(__file__), 'fixtures')
        for file_name in os.listdir(path):
            with open(os.path.join(path, file_name)) as f:
                table_name = FILE_NAME_TO_TABLE_MAPPING[file_name[:-4]]
                table = metadata.tables[table_name]
                postgres_copy.copy_from(f, table, engine, format='csv', null='', header=True)

        try:
            move_ucr_data_into_aggregation_tables(datetime(2017, 5, 28), intervals=2)
        except AssertionError:
            pass
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
