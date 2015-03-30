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


class SqlColumnConfig(object):
    """
    Stub object to send column information to the data source
    """
    def __init__(self, columns, headers=None, warnings=None):
        self.columns = columns
        # default headers to column headers, but allow subclasses to override
        if headers is not None:
            self.headers = [c.header for c in self.columns]
        else:
            self.headers = headers
        self.warnings = warnings if warnings is not None else []


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


def get_expanded_column_config(data_source_configuration, column_config):
    """
    Given a ReportColumn, return a list of DatabaseColumn objects. Each DatabaseColumn
    is configured to show the number of occurrences of one of the values present for
    the ReportColumn's field.

    This function also adds warnings to the column_warnings parameter.

    :param data_source_configuration:
    :param column_config:
    :param column_warnings:
    :return:
    """
    MAXIMUM_EXPANSION = 10
    column_warnings = []
    vals, over_expansion_limit = _get_distinct_values(
        data_source_configuration, column_config, MAXIMUM_EXPANSION
    )
    if over_expansion_limit:
        column_warnings.append(
            'The "{}" column had too many values to expand! '
            'Expansion limited to {} distinct values.'.format(
                column_config.display, MAXIMUM_EXPANSION
            )
        )
    return SqlColumnConfig(_expand_column(column_config, vals), warnings=column_warnings)


def _get_distinct_values(data_source_configuration, column_config, expansion_limit=10):
    """
    Return a tuple. The first item is a list of distinct values in the given
    ReportColumn no longer than expansion_limit. The second is a boolean which
    is True if the number of distinct values in the column is greater than the
    limit.

    :param data_source_configuration:
    :param column_config:
    :param expansion_limit:
    :return:
    """
    too_many_values = False

    session = Session()
    try:
        connection = session.connection()
        table = get_indicator_table(data_source_configuration)
        if not table.exists(bind=connection):
            return [], False
        column = table.c[column_config.field]

        query = sqlalchemy.select([column], limit=expansion_limit + 1).distinct()
        result = connection.execute(query).fetchall()
        distinct_values = [x[0] for x in result]
        if len(distinct_values) > expansion_limit:
            distinct_values = distinct_values[:expansion_limit]
            too_many_values = True
    except:
        session.rollback()
        raise
    finally:
        session.close()

    return distinct_values, too_many_values


def _expand_column(report_column, distinct_values):
    """
    Given a ReportColumn, return a list of DatabaseColumn objects. Each column
    is configured to show the number of occurrences of one of the given distinct_values.

    :param report_column:
    :param distinct_values:
    :return:
    """
    columns = []
    for val in distinct_values:
        columns.append(DatabaseColumn(
            u"{}-{}".format(report_column.display, val),
            SumWhen(
                report_column.field,
                whens={val: 1},
                else_=0,
                alias=u"{}-{}".format(report_column.column_id, val),
            ),
            sortable=False,
            data_slug=u"{}-{}".format(report_column.column_id, val),
            format_fn=report_column.get_format_fn(),
            help_text=report_column.description
        ))
    return columns
