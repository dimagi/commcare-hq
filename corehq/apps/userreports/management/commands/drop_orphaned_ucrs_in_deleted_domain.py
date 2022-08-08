from django.core.management.base import BaseCommand, CommandError

from sqlalchemy.exc import ProgrammingError

from corehq.apps.domain.models import Domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.util import (
    get_domain_for_ucr_table_name,
    get_tables_for_data_sources,
    get_tables_without_data_sources,
)
from corehq.sql_db.connections import connection_manager


class Command(BaseCommand):
    help = "Drop orphaned UCR tables for the specified deleted domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        deleted_domains = Domain.get_deleted_domain_names()
        active_domains = set(Domain.get_all_names())
        is_deleted = domain in deleted_domains and domain not in active_domains
        if not is_deleted:
            raise CommandError(
                f'The domain {domain} is not deleted or has an active conflict. Resolve before trying again.')

        data_sources = list(DataSourceConfiguration.all())
        data_sources.extend(list(StaticDataSourceConfiguration.all()))
        tables_by_engine_id = get_tables_for_data_sources(data_sources, engine_id=None)
        orphaned_tables_by_engine_id = get_tables_without_data_sources(tables_by_engine_id)
        drop_tables_for_domain(domain, orphaned_tables_by_engine_id)


def drop_tables_for_domain(domain, tables_by_engine_id):
    for engine_id, tablenames in tables_by_engine_id.items():
        engine = connection_manager.get_engine(engine_id)

        for tablename in tablenames:
            # double check that table belongs to domain
            if domain != get_domain_for_ucr_table_name(tablename):
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
                    connection.execute(f'DROP TABLE "{tablename}"')
                    print(f'\t^-- deleted {tablename}')
