from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import inspect
import logging
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from sqlalchemy import inspect as sqlinspect

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, UCR_TABLE_PREFIX
from corehq.sql_db.connections import connection_manager
from custom.icds_reports.const import AGG_LS_AWC_VISIT_TABLE, AGG_LS_VHND_TABLE, AGG_LS_BENEFICIARY_TABLE, \
    AGG_GROWTH_MONITORING_TABLE, AGG_DAILY_FEEDING_TABLE, AGG_COMP_FEEDING_TABLE, AGG_CCS_RECORD_CF_TABLE, \
    AGG_CHILD_HEALTH_THR_TABLE, AGG_CCS_RECORD_THR_TABLE, AGG_CHILD_HEALTH_PNC_TABLE, AGG_CCS_RECORD_PNC_TABLE, \
    AGG_CCS_RECORD_DELIVERY_TABLE, AGG_CCS_RECORD_BP_TABLE, AGG_INFRASTRUCTURE_TABLE, AWW_INCENTIVE_TABLE
from custom.icds_reports.models import AggregateInactiveAWW, AggregateSQLProfile, ICDSAuditEntryRecord
from custom.icds_reports.models.helper import IcdsFile

logger = logging.getLogger(__name__)

IGNORE_TABLES = {
    'django_migrations',
    AggregateSQLProfile._meta.db_table,
    'ucr_table_name_mapping',
}

"""
- table get's created with normal django migrations
- create child tables
- dump and load data from individual child tables
"""
keep_child_tables = [
    'agg_awc',
    'agg_child_health',
    'agg_ccs_record',
    AGG_LS_AWC_VISIT_TABLE,
    AGG_LS_VHND_TABLE,
    AGG_LS_BENEFICIARY_TABLE,
    'agg_ls',
    'agg_awc_daily',
    AWW_INCENTIVE_TABLE,
]

"""
- table get's created with normal django migrations
- don't create child tables
- dump from child and load to main table
"""
drop_child_tables = [
    AGG_GROWTH_MONITORING_TABLE,
    AGG_DAILY_FEEDING_TABLE,
    AGG_COMP_FEEDING_TABLE,
    AGG_CCS_RECORD_CF_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_CCS_RECORD_THR_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CCS_RECORD_DELIVERY_TABLE,
    AGG_CCS_RECORD_BP_TABLE,
    'daily_attendance',
    'child_health_monthly',
    'ccs_record_monthly',
    AGG_INFRASTRUCTURE_TABLE,
]

"""
- table get's created with normal django migrations
- dump and load direct
"""
plain_tables = [
    'icds_months',
    'icds_months_local',
    'awc_location',
    'awc_location_local',
    AggregateInactiveAWW._meta.db_table,
    IcdsFile._meta.db_table,
    ICDSAuditEntryRecord._meta.db_table,

]


def get_parent_child_mapping(connection):
    res = connection.execute("""
        SELECT c.relname AS child, p.relname as parent
        FROM pg_inherits JOIN pg_class AS c ON (inhrelid=c.oid)
        JOIN pg_class as p ON (inhparent=p.oid);
    """)

    mapping = defaultdict(list)
    for row in res:
        mapping[row.parent].append(row.child)
    return mapping


def get_all_tables(connection):
    res = connection.execute("select tablename from pg_tables where schemaname = 'public'")
    return {row.tablename for row in res}


def table_exists(connection, table_name):
    res = connection.execute("select 1 from pg_tables where tablename = %s", table_name)
    return bool(list(res))


def get_dump_command(table, rename_to=None):
    dump = 'pg_dump -t {table} $SOURCE_DB $DUMP_OPTS'
    if rename_to:
        dump += ' | sed "s/{table}/{rename_to}/g"'
    dump += ' | psql $CITUS_CONNECT'
    return dump.format(table=table, rename_to=rename_to)


def get_dump_pre_commands(source_config, target_config):
    return inspect.cleandoc("""
    #!/bin/bash

    SOURCE_DB='{source_db}'
    CITUS_CONNECT="-h {target_host} -U {target_user} {target_db}
    DUMP_OPTS="--data-only --no-acl"
    """.format(
        source_db=source_config['NAME'],
        target_host=target_config['HOST'],
        target_user=target_config['USER'],
        target_db=target_config['NAME']
    ))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['update-schema', 'generate-dump-script'],
        )
        parser.add_argument(
            '--source-db-alias', default='icds-ucr',
            help='Django alias for source database'
        )
        parser.add_argument(
            '--target-db-alias', default='icds-ucr-citus',
            help='Django alias for target database'
        )
        parser.add_argument(
            '--citus-user',
            help='PG user to connect to CitusDB as. Defaults to the user in localsettings.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only output logging.',
        )

    def handle(self, action, source_db_alias, target_db_alias, **options):
        self.dry_run = options['dry_run']

        with connection_manager.get_engine(source_db_alias).begin() as conn:
            self.parent_child_mapping = get_parent_child_mapping(conn)
            self.child_parent_mapping = {
                child: parent
                for parent, children in self.parent_child_mapping.items()
                for child in children
            }

        if action == 'update-schema':
            self.update_schema(source_db_alias, target_db_alias)

        elif action == 'generate-dump-script':
            self.generate_dump_script(options, source_db_alias, target_db_alias)

    def generate_dump_script(self, options, source_db_alias, target_db_alias):

        self.seen_tables = set()

        source_config = settings.DATABASES[source_db_alias].copy()
        target_config = settings.DATABASES[target_db_alias].copy()
        if options['citus_user']:
            target_config['USER'] = options['citus_user']
        self.stdout.write(get_dump_pre_commands(source_config, target_config))
        source_engine = connection_manager.get_engine(source_db_alias)
        # direct dump and load from parent + child tables
        with source_engine.begin() as source_conn:
            for table in keep_child_tables + plain_tables:
                for command in self.get_dump_parent_and_children(source_conn, table):
                    self.stdout.write(command)

            # direct dump and load from parent
            # dump from all child tables into parent table
            for table in drop_child_tables:
                for command in self.get_dump_parent_and_children(source_conn, table, all_in_parent=True):
                    self.stdout.write(command)

            for datasource in StaticDataSourceConfiguration.by_domain('icds-cas'):
                adapter = get_indicator_adapter(datasource)
                table_name = adapter.get_table().name

                # direct dump and load from parent
                # dump from all child tables into parent table
                #  - if table is distrubuted, citus will distribute the data
                #  - if table is partitioned the triggers on the parent will distribute the data
                for command in self.get_dump_parent_and_children(source_conn, table_name, all_in_parent=True):
                    self.stdout.write(command)

            all_tables = get_all_tables(source_conn)
            remaining_tables = all_tables - self.seen_tables - IGNORE_TABLES
            icds_ucr_prefix = '{}{}_'.format(UCR_TABLE_PREFIX, 'icds-cas')

            def keep_table(table):
                root_table = self.child_parent_mapping.get(table, table)
                return not root_table.startswith(UCR_TABLE_PREFIX) or root_table.startswith(icds_ucr_prefix)

            remaining_tables = filter(keep_table, remaining_tables)

            if remaining_tables:
                self.stderr.write("Some tables not seen:")
                for t in remaining_tables:
                    parent = self.child_parent_mapping.get(t)
                    if parent:
                        self.stderr.write("\t{} (parent: {})".format(t, parent))
                    else:
                        self.stderr.write("\t{}".format(t))

    def update_schema(self, source_db_alias, target_db_alias):
        source_engine = connection_manager.get_engine(source_db_alias)
        target_engine = connection_manager.get_engine(target_db_alias)
        with source_engine.begin() as source_conn, target_engine.begin() as target_conn:
            for table in keep_child_tables:
                self.create_child_tables(source_conn, target_conn, table)

    def create_child_tables(self, source_connection, target_connection, table_name):
        for child_table in self.parent_child_mapping[table_name]:
            if not table_exists(target_connection, child_table):
                insp = sqlinspect(source_connection)
                constratints = insp.get_check_constraints(child_table)
                sql = """
                    CREATE TABLE IF NOT EXISTS "{tablename}" ({constraint}) INHERITS ("{parent_tablename}")
                """.format(
                    parent_tablename=table_name,
                    tablename=child_table,
                    constraint='CHECK {}'.format(constratints[0]['sqltext']) if constratints else ''
                )
                logging.info(sql)
                if not self.dry_run:
                    source_connection.execute(sql)

    def get_dump_parent_and_children(self, source_connnection, table, all_in_parent=False):
        yield '\n# {}'.format(table)
        yield get_dump_command(table)
        self.seen_tables.add(table)
        for child in self.parent_child_mapping[table]:
            self.seen_tables.add(child)
            yield get_dump_command(child, rename_to=table if all_in_parent else None)
