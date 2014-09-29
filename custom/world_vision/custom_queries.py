import time
import logging
from sqlagg.base import CustomQueryColumn, QueryMeta
from sqlagg.filters import NOTEQ
from sqlagg.queries.alchemy_extensions import InsertFromSelect, func_ext
from sqlagg.queries.median import MedianQueryMeta
from sqlalchemy import select, Table, Column, INT, and_, func, alias
from sqlalchemy.types import DECIMAL
from sqlalchemy import cast, Float

logger = logging.getLogger("sqlagg")

class CustomMeanQueryMeta(QueryMeta):

    def __init__(self, table_name, filters, group_by, key, alias):
        self.key = key
        self.alias = alias
        super(CustomMeanQueryMeta, self).__init__(table_name, filters, group_by)

    def execute(self, metadata, connection, filter_values):
        return connection.execute(self._build_query(filter_values)).fetchall()

    def _build_query(self, filter_values):
        return select(['AVG(%s::float) as %s' % (self.key, self.alias)], from_obj='"fluff_WorldVisionChildFluff"')\
            .where("%s != '' " % self.key)


class CustomMedianQueryMeta(MedianQueryMeta):

    def _build_median_table(self, metadata):
        """
        CREATE TEMP TABLE temp_median (id serial PRIMARY KEY, user_name VARCHAR(50), value INT);
        """
        origin_table = metadata.tables[self.table_name]
        origin_column = origin_table.c[self.key]

        table_name = self._get_table_name("m")
        median_table = Table(table_name, metadata,
                             Column("id", INT, primary_key=True),
                             Column("value", origin_column.type),
                             prefixes=['TEMPORARY'])
        for group in self.group_by:
            column = origin_table.c[group]
            median_table.append_column(Column(group, column.type))

        logger.debug("Building median table: %s", table_name)
        median_table.create()

        return median_table


    def _build_median_table(self, metadata):
        """
        CREATE TEMP TABLE temp_median (id serial PRIMARY KEY, user_name VARCHAR(50), value INT);
        """
        origin_table = metadata.tables[self.table_name]
        origin_column = origin_table.c[self.key]
        table_name = self._get_table_name("m")
        median_table = Table(table_name, metadata,
                             Column("id", INT, primary_key=True),
                             Column("value", DECIMAL),
                             prefixes=['TEMPORARY'])
        for group in self.group_by:
            column = origin_table.c[group]
            median_table.append_column(Column(group, column.type))

        logger.debug("Building median table: %s", table_name)
        median_table.create()

        return median_table


    def _build_median_id_table(self, metadata):
        """
        CREATE TEMPORARY TABLE temp_median_ids (upper INT, lower INT);
        """
        table_name = self._get_table_name("m_id")
        median_id_table = Table(table_name, metadata,
                                Column("upper", INT),
                                Column("lower", INT),
                                prefixes=["TEMPORARY"])

        logger.debug("Building median ID table: %s", table_name)
        median_id_table.create()
        return median_id_table

    def _populate_median_table(self, median_table, metadata, connection, filter_values):
        """
        INSERT INTO temp_median (user_name, value) (
            SELECT t.user_name, indicator_d FROM user_table t ORDER BY t.user_name, indicator_d
        );
        """
        origin_table = metadata.tables[self.table_name]
        origin_column = origin_table.c[self.key]

        query = select([cast(origin_column, Float(2))]).where(origin_column != '')
        for group in self.group_by:
            column = origin_table.c[group]
            query.append_column(column)
            query.append_order_by(column)

        query.append_order_by(origin_table.c[self.key])


        # TODO: better way of escaping names
        columns = ["value"] + self.group_by
        for i, c in enumerate(columns):
            columns[i] = '"%s"' % c

        from_select = InsertFromSelect(median_table, query, columns)

        logger.debug("Populate median table")
        connection.execute(from_select, **filter_values)


class CustomMeanColumn(CustomQueryColumn):
    query_cls = CustomMeanQueryMeta
    name = "mean"

    def get_query_meta(self, default_table_name, default_filters, default_group_by):
        table_name = self.table_name or default_table_name
        filters = self.filters or default_filters
        group_by = self.group_by or default_group_by
        return self.query_cls(table_name, filters, group_by, self.key, self.alias)

class CustomMedianColumn(CustomQueryColumn):
    query_cls = CustomMedianQueryMeta
    name = "median"