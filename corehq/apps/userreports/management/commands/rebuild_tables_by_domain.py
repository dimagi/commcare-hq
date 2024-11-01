from django.core.management.base import BaseCommand

from corehq.apps.userreports import tasks
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)

from django.db import connections
from django.db.utils import ProgrammingError
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)


class Command(BaseCommand):
    help = "Rebuild all user configurable reporting tables in domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--initiated-by', required=True, action='store',
            dest='initiated', help='Who initiated the rebuild'
        )
        parser.add_argument('--only-missing', required=True, action='store_true',
            dest='only_missing', help='should build only missing')

    def get_missing_tables(self, domain, tables):
        missing_tables = []

        for table in tables:
            table_name = get_table_name(domain, table.table_id)
            query = f'select * from "{table_name}" limit 1'
            try:
                _run_custom_sql_script(query)
            except ProgrammingError:
                missing_tables.append(table)
        return missing_tables

    def handle(self, domain, **options):
        tables = StaticDataSourceConfiguration.by_domain(domain)
        tables.extend(DataSourceConfiguration.by_domain(domain))

        if options.get('only_missing'):
            tables_to_build = self.get_missing_tables(domain, tables)
        else:
            tables_to_build = tables

        print("Rebuilding {} tables".format(len(tables_to_build)))

        for table in tables_to_build:
            tasks.rebuild_indicators(
                table._id, initiated_by=options['initiated'], source='rebuild_tables_by_domain'
            )
