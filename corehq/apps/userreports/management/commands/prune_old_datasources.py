from collections import defaultdict

from django.core.management.base import BaseCommand

from sqlalchemy.exc import ProgrammingError

from corehq.apps.domain.models import Domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.util import (
    LEGACY_UCR_TABLE_PREFIX,
    UCR_TABLE_PREFIX,
    get_domain_for_ucr_table_name,
    get_table_name,
)
from corehq.sql_db.connections import connection_manager


class Command(BaseCommand):
    """
    Note that this command does not contain logic to drop tables with data sources that no longer exist. It only
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
        parser.add_argument(
            '--drop-deleted-tables',
            action='store_true',
            default=False,
            help='Call DROP TABLE on tables from deleted domains',
        )

    def handle(self, **options):
        data_sources = list(DataSourceConfiguration.all())
        data_sources.extend(list(StaticDataSourceConfiguration.all()))
        tables_by_engine_id = get_tables_by_engine_id(data_sources, options.get('engine_id'))
        tables_to_remove_by_engine = get_tables_to_remove_by_engine(tables_by_engine_id)
        prune_tables(tables_to_remove_by_engine, options['drop_empty_tables'], options['drop_deleted_tables'])


def prune_tables(tables_to_remove_by_engine, drop_empty_tables, drop_deleted_tables):
    deleted_domains = Domain.get_deleted_domain_names()
    for engine_id, tablenames in tables_to_remove_by_engine.items():
        print("\nTables no longer referenced in database: {}:\n".format(engine_id))
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
            print("\t No tables to prune")
            continue

        for tablename in tablenames:
            should_drop_tables_in_deleted_domains = drop_deleted_tables and get_domain_for_ucr_table_name(
                tablename) in deleted_domains

            with engine.begin() as connection:
                try:
                    result = connection.execute(f'SELECT COUNT(*), MAX(inserted_at) FROM "{tablename}"')
                except ProgrammingError:
                    print(f"\t{tablename}: no inserted_at column, probably not UCR")
                except Exception as e:
                    print(f"\tAn error was encountered when attempting to read from {tablename}: {e}")
                else:
                    row_count, idle_since = result.fetchone()
                    should_drop_empty_tables = drop_empty_tables and row_count == 0
                    if should_drop_tables_in_deleted_domains or should_drop_empty_tables:
                        print(f"\t{tablename}: {row_count} rows")
                        connection.execute(f'DROP TABLE "{tablename}"')
                        print(f'\t^-- deleted {tablename}')
                    else:
                        print(f"\t{tablename}: {row_count} rows, idle since {idle_since}")


def get_tables_by_engine_id(data_sources, engine_id):
    tables_by_engine_id = defaultdict(set)
    for data_source in data_sources:
        if engine_id and data_source.engine_id != engine_id:
            continue

        table_name = get_table_name(data_source.domain, data_source.table_id)
        tables_by_engine_id[data_source.engine_id].add(table_name)

    return tables_by_engine_id


def get_tables_to_remove_by_engine(tables_by_engine_id):
    tables_to_remove_by_engine = defaultdict(list)
    for engine_id, expected_tables in tables_by_engine_id.items():
        engine = connection_manager.get_engine(engine_id)
        with engine.begin() as connection:
            # Using string formatting rather than execute with %s syntax
            # is acceptable here because the strings we're inserting are static
            # and only templated for DRYness
            results = connection.execute(f"""
            SELECT table_name
              FROM information_schema.tables
            WHERE table_schema='public'
              AND table_type='BASE TABLE'
              AND (
                table_name LIKE '{UCR_TABLE_PREFIX}%%'
                OR
                table_name LIKE '{LEGACY_UCR_TABLE_PREFIX}%%'
            );
            """).fetchall()
            tables_in_db = {r[0] for r in results}

        tables_to_remove_by_engine[engine_id] = tables_in_db - expected_tables
    return tables_to_remove_by_engine
