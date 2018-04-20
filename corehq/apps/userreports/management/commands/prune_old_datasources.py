from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict

from alembic.autogenerate.api import compare_metadata
from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.sql.adapter import metadata
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager

from fluff.signals import get_migration_context, reformat_alembic_diffs


class Command(BaseCommand):
    help = "Call DROP TABLE on data sources that no longer exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--engine_id',
            action='store',
            help='Only check this DB engine',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            default=False,
            help='Not implemented: Actually call DROP TABLE',
        )

    def handle(self, **options):
        data_sources = list(DataSourceConfiguration.all())
        data_sources.extend(list(StaticDataSourceConfiguration.all()))

        tables_by_engine = self._get_tables_by_engine(data_sources, options.get('engine_id'))

        tables_to_remove_by_engine = defaultdict(list)
        for engine_id, table_map in tables_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            with engine.begin() as connection:
                migration_context = get_migration_context(connection, include_object=_include_object)
                raw_diffs = compare_metadata(migration_context, metadata)

            diffs = reformat_alembic_diffs(raw_diffs)
            tables_to_remove_by_engine[engine_id] = [
                diff.table_name for diff in diffs
                if diff.type == 'remove_table'
            ]

        for engine_id, tablenames in tables_to_remove_by_engine.items():
            engine = connection_manager.get_engine(engine_id)
            for tablename in tablenames:
                with engine.begin() as connection:
                    try:
                        result = connection.execute(
                            'SELECT COUNT(*), MAX(inserted_at) FROM "{tablename}"'.format(tablename=tablename)
                        )
                    except Exception:
                        print(tablename, "no inserted_at column, probably not UCR")
                    else:
                        print(tablename, result.fetchone())

    def _get_tables_by_engine(self, data_sources, engine_id):
        tables_by_engine = defaultdict(list)
        for data_source in data_sources:
            adapter = get_indicator_adapter(data_source)
            if hasattr(adapter, 'engine_id'):
                if engine_id and engine_id != adapter.engine_id:
                    continue
                tables_by_engine[adapter.engine_id].append(adapter.get_table().name)

        return tables_by_engine


def _include_object(object_, name, type_, reflected, compare_to):
    if type_ != 'table':
        return False

    if not name.startswith('config_report_'):
        return False

    return True
