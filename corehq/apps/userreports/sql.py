import sqlalchemy
from django.conf import settings
from fluff.util import get_column_type

metadata = sqlalchemy.MetaData()


def get_indicator_table(indicator_config):
    sql_columns = [column_to_sql(col) for col in indicator_config.get_columns()]
    table_name = _get_table_name(indicator_config.domain, indicator_config.table_id)
    # todo: needed to add extend_existing=True to support multiple calls to this function for the same table.
    # is that valid?
    return sqlalchemy.Table(
        table_name,
        metadata,
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


def rebuild_table(table):
    engine = get_engine()
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)
    engine.dispose()


def _get_table_name(domain, table_id):
    return 'configurable_indicators_{0}_{1}'.format(domain, table_id)