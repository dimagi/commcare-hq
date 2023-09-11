import logging
from collections import defaultdict

from django.core.management.base import BaseCommand

from sqlalchemy import text

from corehq.apps.userreports.alembic_diffs import DiffTypes
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.pillow_utils import (
    _is_datasource_active,
    get_table_diffs,
)
from corehq.apps.userreports.rebuild import _get_indexes_diffs_to_change
from corehq.apps.userreports.sql import get_metadata
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.sql_db.connections import connection_manager
from corehq.util.log import with_progress_bar

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Adds an index on all `inserted_at` columns of data sources for the specified domain'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--initiated-by',
            action='store',
            required=True,
            dest='initiated_by',
            help='Who initiated the migration',
        )

    def handle(self, domain, initiated_by, *args, **kwargs):
        tables = StaticDataSourceConfiguration.by_domain(domain)
        tables.extend(DataSourceConfiguration.by_domain(domain))
        adapters = []
        for config in tables:
            adapters.append(
                get_indicator_adapter(
                    config, load_source='add_inserted_at_index'
                )
            )

        tables_by_engine = defaultdict(dict)
        for adapter in adapters:
            if _is_datasource_active(adapter):
                tables_by_engine[adapter.engine_id][
                    adapter.get_table().name
                ] = adapter

        for engine_id, table_map in with_progress_bar(tables_by_engine.items(), oneline=False):
            table_names = list(table_map)
            engine = connection_manager.get_engine(engine_id)

            diffs = get_table_diffs(
                engine, table_names, get_metadata(engine_id)
            )
            index_diffs = _get_indexes_diffs_to_change(diffs)
            # Filter for diffs where we 1. add an index to 2. the inserted_at column
            add_index_to_inserted_at_diffs = list(
                filter(
                    lambda diff: diff.type == DiffTypes.ADD_INDEX
                    and hasattr(diff.index.columns, 'inserted_at'),
                    index_diffs,
                )
            )

            index_diff_pairs = [(diff.index, diff) for diff in add_index_to_inserted_at_diffs]
            if not index_diff_pairs:
                continue

            num_diffs_to_attend = len(index_diff_pairs)
            diffs_addressed = []
            try:
                with engine.connect() as connection:
                    connection.execution_options(isolation_level='AUTOCOMMIT')
                    for index, diff in index_diff_pairs:
                        column_names = ', '.join(c.name for c in index.columns)
                        table_name = index.table.name
                        sql_query = f'CREATE INDEX CONCURRENTLY "{index.name}" ON "{table_name}" ({column_names})'
                        connection.execute(text(sql_query))
                        diffs_addressed.append(diff.to_dict())
            except Exception as ex:
                logger.exception(ex)
            finally:
                adapter.log_table_migrate(
                    source='management_command',
                    diffs=diffs_addressed,
                    initiated_by=initiated_by,
                )
                logger.info(f'{len(diffs_addressed)} indexes added')
                if not len(diffs_addressed) == num_diffs_to_attend:
                    num_diffs_not_attended = num_diffs_to_attend - len(
                        diffs_addressed
                    )
                    logger.warning(
                        f'{num_diffs_not_attended} indexes were not added'
                    )
