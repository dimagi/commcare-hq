from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict

from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_table_name, UCR_TABLE_PREFIX, LEGACY_UCR_TABLE_PREFIX
from corehq.sql_db.connections import connection_manager


class Command(BaseCommand):
    help = "Call DROP TABLE on data sources that no longer exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--engine_id',
            action='store',
            help='Only check this DB engine',
        )
        parser.add_argument(
            '--show-counts',
            action='store_true',
            default=False,
            help='Show the row counts for the tables.',
        )

    def handle(self, **options):
        data_sources = list(DataSourceConfiguration.all())
        data_sources.extend(list(StaticDataSourceConfiguration.all()))

        tables_by_engine_id = self._get_tables_by_engine_id(data_sources, options.get('engine_id'))

        tables_to_remove_by_engine = defaultdict(list)
        for engine_id, expected_tables in tables_by_engine_id.items():
            engine = connection_manager.get_engine(engine_id)
            with engine.begin() as connection:
                results = connection.execute("""
                SELECT table_name
                  FROM information_schema.tables
                WHERE table_schema='public'
                  AND table_type='BASE TABLE'
                  AND (
                    table_name LIKE '{}%%'
                    OR
                    table_name LIKE '{}%%'
                );
                """.format(UCR_TABLE_PREFIX, LEGACY_UCR_TABLE_PREFIX)).fetchall()
                tables_in_db = {r[0] for r in results}

            tables_to_remove_by_engine[engine_id] = tables_in_db - expected_tables

        for engine_id, tablenames in tables_to_remove_by_engine.items():
            print("\nTables no longer referenced in database: {}:\n".format(engine_id))
            engine = connection_manager.get_engine(engine_id)
            if not tablenames:
                print("\t No tables to prune")
                continue

            for tablename in tablenames:
                if options['show_counts']:
                    with engine.begin() as connection:
                        try:
                            result = connection.execute(
                                'SELECT COUNT(*), MAX(inserted_at) FROM "{tablename}"'.format(tablename=tablename)
                            )
                        except Exception:
                            print("\t{}: no inserted_at column, probably not UCR".format(tablename))
                        else:
                            print("\t{}: {}".foramt(tablename, result.fetchone()))
                else:
                    print("\t{}".format(tablename))

    def _get_tables_by_engine_id(self, data_sources, engine_id):
        tables_by_engine_id = defaultdict(set)
        for data_source in data_sources:
            if engine_id and data_source.engine_id != engine_id:
                continue

            table_name = get_table_name(data_source.domain, data_source.table_id)
            tables_by_engine_id[data_source.engine_id].add(table_name)

        return tables_by_engine_id
