from __future__ import absolute_import, print_function
from __future__ import unicode_literals

import logging
import re
import sqlite3

from django.core.management import CommandError
from django.core.management.base import BaseCommand
from sqlalchemy import inspect as sqlinspect

from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter, UCR_TABLE_PREFIX
from corehq.sql_db.connections import connection_manager
from custom.icds_reports.const import DASHBOARD_DOMAIN
from custom.icds_reports.management.commands.create_citus_child_tables import keep_child_tables, plain_tables, \
    drop_child_tables, get_parent_child_mapping
from custom.icds_reports.models import AggregateSQLProfile
from six.moves import filter

logger = logging.getLogger(__name__)


IGNORE_TABLES = {
    'django_migrations',
    AggregateSQLProfile._meta.db_table,
    'ucr_table_name_mapping',
}


CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS tables (
        id integer PRIMARY KEY,
        source_table text NOT NULL,
        date text,
        target_table text,
        migrated integer,
        errored integer
    ); """


def get_all_tables(connection):
    res = connection.execute("select tablename from pg_tables where schemaname = 'public'")
    return {row.tablename for row in res}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('output_database')
        parser.add_argument(
            '--source-engine-id', default='icds-ucr',
            help='Django alias for source database'
        )

    def handle(self, output_database, source_engine_id, **options):
        with connection_manager.get_engine(source_engine_id).begin() as conn:
            self.all_tables = get_all_tables(conn)
            self.parent_child_mapping = get_parent_child_mapping(conn)
            self.child_parent_mapping = {
                child: parent
                for parent, children in self.parent_child_mapping.items()
                for child in children
            }

        self.table_count = 0
        self.db = sqlite3.connect(output_database)
        try:
            self.setup_sqlite_db()
            self.generate_dump_script(source_engine_id)
            self.stdout.write("\n{} tables processed\n".format(self.table_count))
        finally:
            self.db.close()

    def setup_sqlite_db(self):
        with self.db:
            self.db.execute(CREATE_TABLE)
            res = self.db.execute('select count(*) from tables')
            if res.fetchone()[0] > 0:
                raise CommandError('Database already has records. Delete it and re-run command.')

    def insert_row(self, row):
        self.table_count += 1
        with self.db:
            self.db.execute('INSERT INTO tables(source_table, date, target_table) values (?,?,?)', row)

    def generate_dump_script(self, source_engine_id):
        self.seen_tables = set()

        source_engine = connection_manager.get_engine(source_engine_id)
        # direct dump and load from parent + child tables
        with source_engine.begin() as source_conn:
            insp = sqlinspect(source_conn)
            for table in keep_child_tables + plain_tables:
                if table in self.all_tables:
                    for line in self.get_table_date_target(insp, table):
                        self.insert_row(line)

            # direct dump and load from parent
            # dump from all child tables into parent table
            for table in drop_child_tables:
                if table in self.all_tables:
                    for line in self.get_table_date_target(insp, table, all_in_parent=True):
                        self.insert_row(line)

            for datasource in StaticDataSourceConfiguration.by_domain(DASHBOARD_DOMAIN):
                if source_engine_id == datasource.engine_id or source_engine_id in datasource.mirrored_engine_ids:
                    adapter = get_indicator_adapter(datasource)
                    table_name = adapter.get_table().name

                    # direct dump and load from parent
                    # dump from all child tables into parent table
                    #  - if table is distrubuted, citus will distribute the data
                    #  - if table is partitioned the triggers on the parent will distribute the data
                    for line in self.get_table_date_target(insp, table_name, all_in_parent=True):
                        self.insert_row(line)

            remaining_tables = self.all_tables - self.seen_tables - IGNORE_TABLES
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
        yield table, None, None
        self.seen_tables.add(table)
        for child in self.parent_child_mapping[table]:
            self.seen_tables.add(child)
            yield child, get_table_date(sql_insepctor, child), table if all_in_parent else None


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
    return date
