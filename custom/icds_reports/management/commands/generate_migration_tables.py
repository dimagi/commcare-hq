from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import logging
import re

from django.core.management.base import BaseCommand
from sqlalchemy import inspect as sqlinspect

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, UCR_TABLE_PREFIX
from corehq.sql_db.connections import connection_manager
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.management.commands.create_citus_child_tables import keep_child_tables, plain_tables, \
    drop_child_tables, get_parent_child_mapping
from custom.icds_reports.models import AggregateSQLProfile

logger = logging.getLogger(__name__)


IGNORE_TABLES = {
    'django_migrations',
    AggregateSQLProfile._meta.db_table,
    'ucr_table_name_mapping',
}


def get_all_tables(connection):
    res = connection.execute("select tablename from pg_tables where schemaname = 'public'")
    return {row.tablename for row in res}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--source-db-alias', default='icds-ucr',
            help='Django alias for source database'
        )

    def handle(self, source_db_alias, **options):
        with connection_manager.get_engine(source_db_alias).begin() as conn:
            self.parent_child_mapping = get_parent_child_mapping(conn)
            self.child_parent_mapping = {
                child: parent
                for parent, children in self.parent_child_mapping.items()
                for child in children
            }

        self.generate_dump_script(source_db_alias)

    def generate_dump_script(self, source_db_alias):
        self.seen_tables = set()

        source_engine = connection_manager.get_engine(source_db_alias)
        # direct dump and load from parent + child tables
        with source_engine.begin() as source_conn:
            insp = sqlinspect(source_conn)
            for table in keep_child_tables + plain_tables:
                for line in self.get_table_date_target(insp, table):
                    self.stdout.write(','.join(line))

            # direct dump and load from parent
            # dump from all child tables into parent table
            for table in drop_child_tables:
                for line in self.get_table_date_target(insp, table, all_in_parent=True):
                    self.stdout.write(','.join(line))

            for datasource in StaticDataSourceConfiguration.by_domain(DASHBOARD_DOMAIN):
                adapter = get_indicator_adapter(datasource)
                table_name = adapter.get_table().name

                # direct dump and load from parent
                # dump from all child tables into parent table
                #  - if table is distrubuted, citus will distribute the data
                #  - if table is partitioned the triggers on the parent will distribute the data
                for line in self.get_table_date_target(insp, table_name, all_in_parent=True):
                    self.stdout.write(','.join(line))

            all_tables = get_all_tables(source_conn)
            remaining_tables = all_tables - self.seen_tables - IGNORE_TABLES
            icds_ucr_prefix = '{}{}_'.format(UCR_TABLE_PREFIX, DASHBOARD_DOMAIN)

            def keep_table(table):
                root_table = self.child_parent_mapping.get(table, table)
                return not root_table.startswith(UCR_TABLE_PREFIX) or root_table.startswith(icds_ucr_prefix)

            remaining_tables = list(filter(keep_table, remaining_tables))

            if remaining_tables:
                self.stderr.write("Some tables not seen:")
                for t in remaining_tables:
                    parent = self.child_parent_mapping.get(t)
                    if parent:
                        self.stderr.write("\t{} (parent: {})".format(t, parent))
                    else:
                        self.stderr.write("\t{}".format(t))

    def get_table_date_target(self, sql_insepctor, table, all_in_parent=False):
        yield table, '', ''
        self.seen_tables.add(table)
        for child in self.parent_child_mapping[table]:
            self.seen_tables.add(child)
            yield child, get_table_date(sql_insepctor, child), table if all_in_parent else ''


def get_table_date(sql_insepctor, table):
    def _get_date(string):
        match = re.match(r'.*(\d{4}-\d{2}-\d{2}).*', string)
        if match:
            return match.groups()[0]

    date = _get_date(table)
    if not date:
        constraints = [
            constraint for constraint in sql_insepctor.get_check_constraints(table)
            if constraint['name'].startswith(table)
        ]
        if constraints:
            date = _get_date(constraints[0]['sqltext'])
    return date or ''
