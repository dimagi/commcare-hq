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
    An orphaned UCR table is one where the related datasource no longer exists
    This command is designed to delete orphaned tables
    """
    help = "Delete orphaned UCR tables"

    def add_arguments(self, parser):
        parser.add_argument(
            '--engine_id',
            action='store',
            help='Only check this DB engine',
        )
        parser.add_argument(
            '--force-delete',
            action='store_true',
            default=False,
            help='Drop orphaned tables on active domains'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not modify the DB if set to true',
        )

    def handle(self, **options):
        data_sources = list(DataSourceConfiguration.all())
        data_sources.extend(list(StaticDataSourceConfiguration.all()))
        tables_by_engine_id = get_tables_for_data_sources(data_sources, options.get('engine_id'))
        orphaned_tables_by_engine_id = get_tables_without_data_sources(tables_by_engine_id)
        drop_tables(orphaned_tables_by_engine_id, force_delete=options['force_delete'], dry_run=True)
        if not options['dry_run'] and input("Are you sure you want to run the delete operation? (y/n)") == 'y':
            drop_tables(orphaned_tables_by_engine_id, force_delete=options['force_delete'])
        else:
            exit(0)


def drop_tables(tables_to_remove_by_engine, force_delete=False, dry_run=False):
    """
    :param tables_to_remove_by_engine: {'<engine_id>': [<tablename>, ...]}
    :param force_delete: if True, delete orphaned tables for active domains
    :param dry_run: if True, do not make changes to the DB
    """
    if dry_run:
        print("\n---- DRY RUN ----\n")
    for engine_id, tablenames in tables_to_remove_by_engine.items():
        print(f"Looking at database {engine_id}")
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
            print("\tNo tables to delete")
            continue

        for tablename in tablenames:
            domain = get_domain_for_ucr_table_name(tablename)
            if not force_delete and not is_domain_deleted(domain):
                print(
                    f"The domain {domain} is not deleted or has an active conflict. If you are sure "
                    f"you want to delete {tablename}, re-run with the '--force-delete' option. Skipping for now."
                )
                continue

            with engine.begin() as connection:
                try:
                    result = connection.execute(f'SELECT COUNT(*), MAX(inserted_at) FROM "{tablename}"')
                except ProgrammingError:
                    print(f"\t{tablename}: no inserted_at column, probably not UCR")
                except Exception as e:
                    print(f"\tAn error was encountered when attempting to read from {tablename}: {e}")
                else:
                    row_count, idle_since = result.fetchone()
                    print(f"\t{tablename}: {row_count} rows")
                    if not dry_run:
                        connection.execute(f'DROP TABLE "{tablename}"')
                    print(f'\t^-- deleted {tablename}')
    if dry_run:
        print("\n---- DRY RUN COMPLETE ----")


def is_domain_deleted(domain):
    """
    Ensure that the domain exists in the deleted_domain view, AND not in the active domain view
    :param domain:
    :return: True if deleted, False if not
    """
    deleted_domains = Domain.get_deleted_domain_names()
    active_domains = set(Domain.get_all_names())
    return domain in deleted_domains and domain not in active_domains


def get_tables_for_data_sources(data_sources, engine_id):
    """
    :param data_sources:
    :param engine_id: optional parameter to limit results to one db engine
    :return: a dictionary in the form of {<engine_id>: [<tables>], ...}
    """
    tables_by_engine_id = defaultdict(set)
    for data_source in data_sources:
        if engine_id and data_source.engine_id != engine_id:
            continue

        table_name = get_table_name(data_source.domain, data_source.table_id)
        tables_by_engine_id[data_source.engine_id].add(table_name)

    return tables_by_engine_id


def get_tables_without_data_sources(tables_by_engine_id):
    """
    :param tables_by_engine_id:
    :return: a dictionary in the form of {<engine_id>: [<tables], ...}
    """
    tables_without_data_sources = defaultdict(list)
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
        tables_without_data_sources[engine_id] = tables_in_db - expected_tables
    return tables_without_data_sources
