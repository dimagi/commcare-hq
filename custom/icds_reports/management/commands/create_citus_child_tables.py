from __future__ import absolute_import, print_function
from __future__ import unicode_literals

from collections import defaultdict

from django.core.management.base import BaseCommand
from sqlalchemy import inspect as sqlinspect

from corehq.sql_db.connections import connection_manager
from custom.icds_reports.const import AGG_LS_AWC_VISIT_TABLE, AGG_LS_VHND_TABLE, AGG_LS_BENEFICIARY_TABLE, \
    AGG_GROWTH_MONITORING_TABLE, AGG_DAILY_FEEDING_TABLE, AGG_COMP_FEEDING_TABLE, AGG_CCS_RECORD_CF_TABLE, \
    AGG_CHILD_HEALTH_THR_TABLE, AGG_CCS_RECORD_THR_TABLE, AGG_CHILD_HEALTH_PNC_TABLE, AGG_CCS_RECORD_PNC_TABLE, \
    AGG_CCS_RECORD_DELIVERY_TABLE, AGG_CCS_RECORD_BP_TABLE, AGG_INFRASTRUCTURE_TABLE, AWW_INCENTIVE_TABLE
from custom.icds_reports.models import AggregateInactiveAWW, ICDSAuditEntryRecord
from custom.icds_reports.models.helper import IcdsFile

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
    ICDSAuditEntryRecord._meta.db_table,
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


def table_exists(connection, table_name):
    res = connection.execute("select 1 from pg_tables where tablename = %s", table_name)
    return bool(list(res))


class Command(BaseCommand):
    help = "Compare tables in PG and CitusDB and create missing child tables in Citus."

    def add_arguments(self, parser):
        parser.add_argument(
            '-s', '--source-db-alias', default='icds-ucr',
            help='Django alias for source database'
        )
        parser.add_argument(
            '-t', '--target-db-alias', default='icds-ucr-citus',
            help='Django alias for target database'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only output the commands.',
        )

    def handle(self, source_db_alias, target_db_alias, **options):
        self.dry_run = options['dry_run']

        with connection_manager.get_engine(source_db_alias).begin() as conn:
            self.parent_child_mapping = get_parent_child_mapping(conn)

        source_engine = connection_manager.get_engine(source_db_alias)
        target_engine = connection_manager.get_engine(target_db_alias)
        with source_engine.begin() as source_conn:
            for table in keep_child_tables:
                self.create_child_tables(source_conn, target_engine, table)

    def create_child_tables(self, source_connection, target_engine, table_name):
        for child_table in self.parent_child_mapping[table_name]:
            with target_engine.begin() as target_conn:
                if not table_exists(target_conn, child_table):
                    insp = sqlinspect(source_connection)
                    # only interested in child table constraint and not inherited
                    constraints = [
                        constraint for constraint in insp.get_check_constraints(child_table)
                        if constraint['name'].startswith(child_table)
                    ]
                    constraints_sql = [
                        'CHECK ({})'.format(constraint['sqltext'])
                        for constraint in constraints
                    ]
                    sql = """
                        CREATE TABLE IF NOT EXISTS "{tablename}" (
                            {constraints},
                            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
                        ) INHERITS ("{parent_tablename}")
                    """.format(
                        parent_tablename=table_name,
                        tablename=child_table,
                        constraints=', '.join(constraints_sql)
                    )
                    self.stdout.write(sql)
                    if not self.dry_run:
                        target_conn.execute(sql)
