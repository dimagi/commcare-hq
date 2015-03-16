import hashlib
from sqlagg import CustomQueryColumn, QueryMeta, SimpleSqlColumn, SumWhen
import sqlalchemy
from django.conf import settings
from sqlalchemy.exc import IntegrityError
from dimagi.utils.decorators.memoized import memoized
from fluff.util import get_column_type

metadata = sqlalchemy.MetaData()


class IndicatorSqlAdapter(object):

    def __init__(self, engine, config):
        self.engine = engine
        self.config = config

    @memoized
    def get_table(self):
        return get_indicator_table(self.config)

    def rebuild_table(self):
        rebuild_table(self.engine, self.get_table())

    def drop_table(self):
        with self.engine.begin() as connection:
            self.get_table().drop(connection, checkfirst=True)

    def save(self, doc):
        indicator_rows = self.config.get_all_values(doc)
        if indicator_rows:
            table = self.get_table()
            for indicator_row in indicator_rows:
                with self.engine.begin() as connection:
                    # delete all existing rows for this doc to ensure we aren't left with stale data
                    delete = table.delete(table.c.doc_id == doc['_id'])
                    connection.execute(delete)
                    all_values = {i.column.id: i.value for i in indicator_row}
                    insert = table.insert().values(**all_values)
                    try:
                        connection.execute(insert)
                    except IntegrityError:
                        # Someone beat us to it. Concurrent inserts can happen
                        # when a doc is processed by the celery rebuild task
                        # at the same time as the pillow.
                        pass

    def delete(self, doc):
        table = self.get_table()
        with self.engine.begin() as connection:
            delete = table.delete(table.c.doc_id == doc['_id'])
            connection.execute(delete)


def get_indicator_table(indicator_config, custom_metadata=None):
    sql_columns = [column_to_sql(col) for col in indicator_config.get_columns()]
    table_name = get_table_name(indicator_config.domain, indicator_config.table_id)
    # todo: needed to add extend_existing=True to support multiple calls to this function for the same table.
    # is that valid?
    return sqlalchemy.Table(
        table_name,
        custom_metadata or metadata,
        extend_existing=True,
        *sql_columns
    )


def column_to_sql(column):
    return sqlalchemy.Column(
        column.id,
        get_column_type(column.datatype),
        nullable=column.is_nullable,
        primary_key=column.is_primary_key,
    )


def get_engine():
    return sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)


def rebuild_table(engine, table):
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)
    engine.dispose()


def get_column_name(path):
    parts = path.split("/")

    def _hash(parts):
        front = "/".join(parts[:-1])
        end = parts[-1]
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(front).hexdigest(), end)).hexdigest()[:8]

    return "_".join(parts + [_hash(parts)])


def get_table_name(domain, table_id):
    def _hash(domain, table_id):
        return hashlib.sha1('{}_{}'.format(hashlib.sha1(domain).hexdigest(), table_id)).hexdigest()[:8]

    return 'config_report_{0}_{1}_{2}'.format(domain, table_id, _hash(domain, table_id))


class ExpandColumnMeta(QueryMeta):

    def __init__(self, table_name, filters, group_by):
        super(ExpandColumnMeta, self).__init__(table_name, filters, group_by)
        self.columns = []

    def append_column(self, column):
        self.columns.append(column.sql_column)

    @property
    def group_columns(self):
        group_cols = []
        if self.group_by:
            groups = list(self.group_by)
            for g in groups:
                group_cols.append(SimpleSqlColumn(g, aggregate_fn=None, alias=g))
        return group_cols

    def execute(self, metadata, connection, filter_values):
        # TODO: Do it all in one query
        # TODO: Should I be using the column aliases anywhere here?

        table = metadata.tables[self.table_name]

        distinct_values = {}
        for c in self.columns:
            query = sqlalchemy.select().distinct()
            query.append_column(c.build_column(table))
            result = connection.execute(query, **filter_values).fetchall()
            distinct_values[c.column_name] = [v[0] for v in result]

        query = sqlalchemy.select()

        for c in self.columns:
            for val in distinct_values[c.column_name]:
                query.append_column(SumWhen(
                    c.column_name,
                    whens={val: 1},
                    alias="{}-{}".format(c.alias, val),
                    else_=0
                ).sql_column.build_column(table))

        for c in self.group_columns:
            query.append_column(c.build_column(table))
        for grp in self.group_by:
            query.append_group_by(table.c[grp])

        return connection.execute(query, **filter_values).fetchall()


class ExpandColumn(CustomQueryColumn):
    """
    Custom Column that "expands".
    """
    query_cls = ExpandColumnMeta
    name = "expand"

    # TODO: overwrite self.sql_column ??
    # TODO: overwrite self.column_key ??


