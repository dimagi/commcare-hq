import sqlalchemy
from sqlagg import SumWhen

from sqlalchemy.dialects import postgresql

from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn
from corehq.apps.userreports.sql.util import decode_column_name


def column_to_sql(column):
    column_name = decode_column_name(column)
    return sqlalchemy.Column(
        column_name,
        get_column_type(column.datatype),
        nullable=column.is_nullable,
        primary_key=column.is_primary_key,
        index=column.create_index,
    )


def expand_column(report_column, distinct_values, lang):
    columns = []
    for index, val in enumerate(distinct_values):
        alias = "{}-{}".format(report_column.column_id, index)
        if val is None:
            sql_agg_col = SumWhen(
                whens=[['"{}" is NULL'.format(report_column.field), 1]], else_=0, alias=alias
            )
        else:
            sql_agg_col = SumWhen(report_column.field, whens=[[val, 1]], else_=0, alias=alias)

        columns.append(UCRExpandDatabaseSubcolumn(
            "{}-{}".format(report_column.get_header(lang), val),
            agg_column=sql_agg_col,
            expand_value=val,
            sortable=False,
            data_slug="{}-{}".format(report_column.column_id, index),
            format_fn=report_column.get_format_fn(),
            help_text=report_column.description
        ))
    return columns


def get_column_type(data_type):
    if data_type == TYPE_DATE:
        return sqlalchemy.Date
    if data_type == TYPE_DATETIME:
        return sqlalchemy.DateTime
    if data_type == TYPE_INTEGER:
        return sqlalchemy.Integer
    if data_type == TYPE_SMALL_INTEGER:
        return sqlalchemy.SmallInteger
    if data_type == TYPE_DECIMAL:
        return sqlalchemy.Numeric(precision=64, scale=16)
    if data_type == TYPE_STRING:
        return sqlalchemy.UnicodeText
    if data_type == TYPE_ARRAY:
        return postgresql.ARRAY(sqlalchemy.UnicodeText)

    raise Exception('Unexpected type: {0}'.format(data_type))


TYPE_INTEGER = 'integer'
TYPE_SMALL_INTEGER = 'small_integer'
TYPE_DECIMAL = 'decimal'
TYPE_STRING = 'string'
TYPE_DATE = 'date'
TYPE_DATETIME = 'datetime'
TYPE_ARRAY = 'array'
