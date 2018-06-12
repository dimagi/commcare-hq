from __future__ import absolute_import, unicode_literals
import sqlalchemy
from memoized import memoized

from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.userreports.sql.columns import column_to_sql
from corehq.apps.userreports.util import get_table_name


class AggregateIndicatorSqlAdapter(IndicatorSqlAdapter):

    @memoized
    def get_table(self):
        return get_aggregate_table(self.config)


def get_aggregate_table(aggregate_spec):
    sql_columns = [column_to_sql(col) for col in aggregate_spec.get_columns()]
    table_name = get_table_name(aggregate_spec.domain, aggregate_spec.table_id)
    # todo: eventually we might need to add index support here similar to standard UCR tables
    # we might also need support for custom metadata
    return sqlalchemy.Table(
        table_name,
        sqlalchemy.MetaData(),
        *sql_columns
    )


def aggregate_column_to_sql(column_adapter):
    return column_to_sql(column_adapter.get_ucr_column())
