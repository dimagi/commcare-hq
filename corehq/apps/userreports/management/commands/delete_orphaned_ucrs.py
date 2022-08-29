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

    def handle(self, **options):
        orphaned_tables_by_engine_id = get_orphaned_tables_by_engine_id(options.get('engine_id'))
        ucrs_to_delete = get_deletable_ucrs(orphaned_tables_by_engine_id, force_delete=options['force_delete'])
        tablenames_to_drop = confirm_deletion_with_user(ucrs_to_delete)
        if not tablenames_to_drop:
            exit(0)

        drop_tables(tablenames_to_drop)


def confirm_deletion_with_user(ucrs_to_delete):
    if not ucrs_to_delete:
        print("There aren't any UCRs to delete.")

    tablenames_to_drop = defaultdict(list)
    print("The following UCRs will be deleted:\n")
    for engine_id, ucr_infos in ucrs_to_delete.items():
        print(f"\tFrom the {engine_id} database:")
        for ucr_info in ucr_infos:
            print(f"\t\t{ucr_info['tablename']} with {ucr_info['row_count']} rows.")
            tablenames_to_drop[engine_id].append(ucr_info['tablename'])

    if get_input("Are you sure you want to run the delete operation? (y/n)") == 'y':
        return tablenames_to_drop

    return []


def get_orphaned_tables_by_engine_id(engine_id=None):
    """
    :param engine_id: optional parameter to only search within a specific database
    :return: {<engine_id>: [<tablename>, ...]}
    """
    data_sources = get_all_data_sources()
    tables_by_engine_id = get_tables_for_data_sources(data_sources, engine_id)
    return get_tables_without_data_sources(tables_by_engine_id)


def get_all_data_sources():
    data_sources = list(DataSourceConfiguration.all())
    data_sources.extend(list(StaticDataSourceConfiguration.all()))
    return data_sources


def get_deletable_ucrs(orphaned_tables_by_id, force_delete=False):
    """
    Ensures tables are UCRs via inserted_at column
    :param orphaned_tables_by_id: {<engine_id>: [<tablename>, ...]}
    :param force_delete: if True, orphaned tables associated with active domains are marked as deletable
    :return:
    """
    ucrs_to_delete = defaultdict(list)
    for engine_id, tablenames in orphaned_tables_by_id.items():
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
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
                    ucrs_to_delete[engine_id].append({'tablename': tablename, 'row_count': row_count})

    return ucrs_to_delete


def drop_tables(ucrs_to_delete):
    """
    :param ucrs_to_delete: {'<engine_id>': [<tablename>, ...]}
    """
    for engine_id, tablenames in ucrs_to_delete.items():
        engine = connection_manager.get_engine(engine_id)
        if not tablenames:
            continue

        for tablename in tablenames:
            with engine.begin() as connection:
                connection.execute(f'DROP TABLE "{tablename}"')
                print(f'\t^-- deleted {tablename}')


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


def get_input(message):
    return input(message)
