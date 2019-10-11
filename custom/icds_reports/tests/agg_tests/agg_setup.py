import os
from datetime import datetime

import postgres_copy
import sqlalchemy
from django.conf import settings

from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.sql_db.connections import connection_manager, ICDS_UCR_CITUS_ENGINE_ID
from custom.icds_reports.const import DISTRIBUTED_TABLES, REFERENCE_TABLES
from custom.icds_reports.utils.migrations import create_citus_reference_table, create_citus_distributed_table
from custom.icds_reports.tasks import (
    _aggregate_child_health_pnc_forms,
    _aggregate_bp_forms,
    _aggregate_gm_forms
)


FILE_NAME_TO_TABLE_MAPPING = {
    'awc_mgmt': get_table_name('icds-cas', 'static-awc_mgt_forms'),
    "ccs_cases": get_table_name('icds-cas', 'static-ccs_record_cases'),
    'child_cases': get_table_name('icds-cas', 'static-child_health_cases'),
    'daily_feeding': get_table_name('icds-cas', 'static-daily_feeding_forms'),
    'household_cases': get_table_name('icds-cas', 'static-household_cases'),
    'infrastructure': get_table_name('icds-cas', 'static-infrastructure_form'),
    'infrastructure_v2': get_table_name('icds-cas', 'static-infrastructure_form_v2'),
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
    'birth_preparedness': get_table_name('icds-cas', 'static-dashboard_birth_preparedness_forms'),
    'delivery_form': get_table_name('icds-cas', 'static-dashboard_delivery_forms'),
    'thr_form_v2': get_table_name('icds-cas', 'static-thr_forms_v2'),
    'awc_location': 'awc_location',
    'awc_location_local': 'awc_location_local',
    'agg_awc': 'agg_awc',
}


def setup_location_hierarchy(domain_name):
    SQLLocation.objects.all().delete()
    LocationType.objects.all().delete()
    state_location_type = LocationType.objects.create(
        domain=domain_name,
        name='state',
    )
    st1 = SQLLocation.objects.create(
        domain=domain_name,
        name='st1',
        location_id='st1',
        location_type=state_location_type
    )
    st2 = SQLLocation.objects.create(
        domain=domain_name,
        name='st2',
        location_id='st2',
        location_type=state_location_type
    )
    st3 = SQLLocation.objects.create(
        domain=domain_name,
        name='st3',
        location_id='st3',
        location_type=state_location_type
    )
    st4 = SQLLocation.objects.create(
        domain=domain_name,
        name='st4',
        location_id='st4',
        location_type=state_location_type
    )
    st5 = SQLLocation.objects.create(
        domain=domain_name,
        name='st5',
        location_id='st5',
        location_type=state_location_type
    )
    st6 = SQLLocation.objects.create(
        domain=domain_name,
        name='st6',
        location_id='st6',
        location_type=state_location_type
    )
    st7 = SQLLocation.objects.create(
        domain=domain_name,
        name='st7',
        location_id='st7',
        location_type=state_location_type
    )
    # exercise the logic that excludes test states by creating one
    test_state = SQLLocation.objects.create(
        domain=domain_name,
        name='test_state',
        location_id='test_state',
        location_type=state_location_type,
        metadata={
            'is_test_location': 'test',
        }
    )

    district_location_type = LocationType.objects.create(
        domain=domain_name,
        name='district',
        parent_type=state_location_type,
    )
    d1 = SQLLocation.objects.create(
        domain=domain_name,
        name='d1',
        location_id='d1',
        location_type=district_location_type,
        parent=st1
    )

    block_location_type = LocationType.objects.create(
        domain=domain_name,
        name='block',
        parent_type=district_location_type,
    )
    b1 = SQLLocation.objects.create(
        domain=domain_name,
        name='b1',
        location_id='b1',
        location_type=block_location_type,
        parent=d1
    )

    supervisor_location_type = LocationType.objects.create(
        domain=domain_name,
        name='supervisor',
        parent_type=state_location_type,
    )
    s1 = SQLLocation.objects.create(
        domain=domain_name,
        name='s1',
        location_id='s1',
        location_type=supervisor_location_type,
        parent=b1,
    )

    awc_location_type = LocationType.objects.create(
        domain=domain_name,
        name='awc',
        parent_type=supervisor_location_type,
    )
    a7 = SQLLocation.objects.create(
        domain=domain_name,
        name='a7',
        location_id='a7',
        location_type=awc_location_type,
        parent=s1,
    )


def setup_tables_and_fixtures(domain_name):
    configs = StaticDataSourceConfiguration.by_domain(domain_name)
    adapters = [get_indicator_adapter(config) for config in configs]

    for adapter in adapters:
        try:
            adapter.drop_table()
        except Exception:
            pass
        adapter.build_table()

    engine = connection_manager.get_engine(ICDS_UCR_CITUS_ENGINE_ID)
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
                postgres_copy.copy_from(f, table, engine, format='csv', null='', columns=columns)

    _distribute_tables_for_citus(engine)


def _distribute_tables_for_citus(engine):
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


def aggregate_state_form_data():
    for state_id in ('st1', 'st2'):
        _aggregate_child_health_pnc_forms(state_id, datetime(2017, 3, 31))
        _aggregate_bp_forms(state_id, datetime(2017, 3, 31))

    _aggregate_gm_forms(datetime(2017, 3, 31))
