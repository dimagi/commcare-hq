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
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from custom.icds_reports.const import DISTRIBUTED_TABLES, REFERENCE_TABLES

from custom.icds_reports.tasks import (
    move_ucr_data_into_aggregation_tables,
    build_incentive_report,
    _aggregate_child_health_pnc_forms,
    _aggregate_bp_forms,
    _aggregate_gm_forms)
from io import open
from six.moves import range
from six.moves import zip

from custom.icds_reports.utils.migrations import create_citus_reference_table, create_citus_distributed_table

FILE_NAME_TO_TABLE_MAPPING = {
    'awc_mgmt': get_table_name('icds-cas', 'static-awc_mgt_forms'),
    "ccs_cases": get_table_name('icds-cas', 'static-ccs_record_cases'),
    'child_cases': get_table_name('icds-cas', 'static-child_health_cases'),
    'daily_feeding': get_table_name('icds-cas', 'static-daily_feeding_forms'),
    'household_cases': get_table_name('icds-cas', 'static-household_cases'),
    'infrastructure': get_table_name('icds-cas', 'static-infrastructure_form'),
    'infrastructure_v2': get_table_name('icds-cas', 'static-infrastructure_form_v2'),
    'location_ucr': get_table_name('icds-cas', 'static-awc_location'),
    'person_cases': get_table_name('icds-cas', 'static-person_cases_v3'),
    'usage': get_table_name('icds-cas', 'static-usage_forms'),
    'vhnd': get_table_name('icds-cas', 'static-vhnd_form'),
    'complementary_feeding': get_table_name('icds-cas', 'static-complementary_feeding_forms'),
    'aww_user': get_table_name('icds-cas', 'static-commcare_user_cases'),
    'child_tasks': get_table_name('icds-cas', 'static-child_tasks_cases'),
    'pregnant_tasks': get_table_name('icds-cas', 'static-pregnant-tasks_cases'),
    'thr_form': get_table_name('icds-cas', 'static-dashboard_thr_forms'),
    'gm_form': get_table_name('icds-cas', 'static-dashboard_growth_monitoring_forms'),
    'pnc_forms': get_table_name('icds-cas', 'static-postnatal_care_forms'),
    'dashboard_daily_feeding': get_table_name('icds-cas', 'dashboard_child_health_daily_feeding_forms'),
    'ls_awc_mgt': get_table_name('icds-cas', 'static-awc_mgt_forms'),
    'ls_home_vists': get_table_name('icds-cas', 'static-ls_home_visit_forms_filled'),
    'ls_vhnd': get_table_name('icds-cas', 'static-ls_vhnd_form'),
    'cbe_form': get_table_name('icds-cas', 'static-cbe_form'),
    'agg_awc': 'agg_awc',
    'birth_preparedness': get_table_name('icds-cas', 'static-dashboard_birth_preparedness_forms'),
    'delivery_form': get_table_name('icds-cas', 'static-dashboard_delivery_forms'),
}

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'outputs')

_use_citus = override_settings(ICDS_USE_CITUS=True)


def setUpModule():
    if settings.USE_PARTITIONED_DATABASE:
        print('============= WARNING: not running test setup because settings.USE_PARTITIONED_DATABASE is True.')
        return

    _call_center_domain_mock = mock.patch(
        'corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider'
    )
    _call_center_domain_mock.start()
    # _use_citus.enable()

    domain = create_domain('icds-cas')
    SQLLocation.objects.all().delete()
    LocationType.objects.all().delete()
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

    with override_settings(SERVER_ENVIRONMENT='icds'):
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

        _distribute_tables_for_citus(engine)

        for state_id in ('st1', 'st2'):
            _aggregate_child_health_pnc_forms(state_id, datetime(2017, 3, 31))
            _aggregate_gm_forms(state_id, datetime(2017, 3, 31))
            _aggregate_bp_forms(state_id, datetime(2017, 3, 31))

        try:
            move_ucr_data_into_aggregation_tables(datetime(2017, 5, 28), intervals=2)
            build_incentive_report(agg_date=datetime(2017, 5, 28))
        except Exception as e:
            print(e)
            tearDownModule()
            raise
        finally:
            _call_center_domain_mock.stop()


def _distribute_tables_for_citus(engine):
    if not getattr(settings, 'ICDS_USE_CITUS', False):
        return

    for table, col in DISTRIBUTED_TABLES:
        with engine.begin() as conn:

            # TODO: remove this after citus migration
            res = conn.execute(
                """
                SELECT c.relname AS child
                FROM
                    pg_inherits JOIN pg_class AS c ON (inhrelid=c.oid)
                    JOIN pg_class as p ON (inhparent=p.oid)
                    where p.relname = %s;
                """,
                table
            )
            for child in [row.child for row in res]:
                # only need this because of reusedb if testing on master and this branch
                conn.execute('drop table if exists "{}"'.format(child))

            create_citus_distributed_table(conn, table, col)

    for table in REFERENCE_TABLES:
        with engine.begin() as conn:
            create_citus_reference_table(conn, table)


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
    # _use_citus.disable()
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
