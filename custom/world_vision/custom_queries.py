import logging
from sqlagg.base import CustomQueryColumn, BaseColumn
from sqlagg.queries.alchemy_extensions import InsertFromSelect
from sqlagg.queries.median import MedianQueryMeta
from sqlalchemy import select, Table, Column, INT, func
from sqlalchemy.types import DECIMAL, Numeric
from sqlalchemy import cast, Float

logger = logging.getLogger("sqlagg")

class MeanColumnWithCasting(BaseColumn):
    aggregate_fn = lambda _, column: func.avg(cast(column, Numeric(4, 2)))

class CustomMedianQueryMeta(MedianQueryMeta):

    def __init__(self, table_name, filters, group_by, order_by):
        super(CustomMedianQueryMeta, self).__init__(table_name, filters, group_by, order_by)

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


class CustomMedianColumn(CustomQueryColumn):
    query_cls = CustomMedianQueryMeta
    name = "median"
