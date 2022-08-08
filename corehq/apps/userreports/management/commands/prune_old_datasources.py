from django.core.management.base import BaseCommand

from sqlalchemy.exc import ProgrammingError

from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.util import (
    get_tables_for_data_sources,
    get_tables_without_data_sources,
)
from corehq.sql_db.connections import connection_manager


class Command(BaseCommand):
    """
    Note that this command does not contain logic to drop tables with data sources that no longer exist. It
    currently only finds them.
    """
    help = "Find orphaned UCR tables for data sources that no longer exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--engine_id',
            action='store',
            help='Only check this DB engine',
        )
        parser.add_argument(
            '--drop-empty-tables',
            action='store_true',
            default=False,
            help='Call DROP TABLE on tables with no rows',
        )

    def handle(self, **options):
        data_sources = list(DataSourceConfiguration.all())
        data_sources.extend(list(StaticDataSourceConfiguration.all()))
        tables_by_engine_id = get_tables_for_data_sources(data_sources, options.get('engine_id'))
        tables_to_remove_by_engine = get_tables_without_data_sources(tables_by_engine_id)
        prune_tables(tables_to_remove_by_engine, options['drop_empty_tables'])


def prune_tables(tables_to_remove_by_engine, drop_empty_tables):
    for engine_id, tablenames in tables_to_remove_by_engine.items():
        print("\nTables no longer referenced in database: {}:\n".format(engine_id))
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
            print("\t No tables to prune")
            continue

        for tablename in tablenames:
            with engine.begin() as connection:
                try:
                    result = connection.execute(f'SELECT COUNT(*), MAX(inserted_at) FROM "{tablename}"')
                except ProgrammingError:
                    print(f"\t{tablename}: no inserted_at column, probably not UCR")
                except Exception as e:
                    print(f"\tAn error was encountered when attempting to read from {tablename}: {e}")
                else:
                    row_count, idle_since = result.fetchone()
                    if drop_empty_tables and row_count == 0:
                        print(f"\t{tablename}: {row_count} rows")
                        connection.execute(f'DROP TABLE "{tablename}"')
                        print(f'\t^-- deleted {tablename}')
                    else:
                        print(f"\t{tablename}: {row_count} rows, idle since {idle_since}")
