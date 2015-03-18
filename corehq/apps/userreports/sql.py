import hashlib
from sqlagg import SumWhen
import sqlalchemy
from django.conf import settings
from sqlalchemy.exc import IntegrityError
from corehq.db import Session
from corehq.apps.reports.sqlreport import DatabaseColumn
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


def get_expanded_columns(table_name, column_config):

    session = Session()
    connection = session.connection()
    metadata = sqlalchemy.MetaData()
    metadata.reflect(bind=connection)

    column = metadata.tables[table_name].c[column_config.get_sql_column().view.name]
    query = sqlalchemy.select([column]).distinct()

    result = connection.execute(query).fetchall()
    distinct_values = [x[0] for x in result]

    columns = []
    for val in distinct_values:
        columns.append(DatabaseColumn(
            u"{}-{}".format(column_config.display, val),
            SumWhen(
                column_config.field,
                whens={val: 1},
                else_=0,
                # TODO: What is the proper alias?
                # It looks like this alias needs to match data_slug
                alias=u"{}-{}".format(column_config.field, val),
            ),
            sortable=False,
            # TODO: Should this be column_config.report_column_id?
            # It looks like this data_slug needs to match alias
            data_slug=u"{}-{}".format(column_config.field, val),
            format_fn=column_config.get_format_fn(),
            help_text=column_config.description
        ))
    return columns
