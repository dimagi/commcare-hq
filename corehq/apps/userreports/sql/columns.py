from __future__ import absolute_import
from __future__ import unicode_literals

import six
import sqlalchemy
from sqlagg import SumWhen
from fluff import TYPE_STRING
from fluff.util import get_column_type

from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn
from corehq.apps.userreports.sql.util import decode_column_name

def column_to_sql(column):
    column_name = decode_column_name(column)
    return sqlalchemy.Column(
        column_name,
        _get_column_type(column.datatype),
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
                whens={'"{}" is NULL'.format(report_column.field): 1}, else_=0, alias=alias
            )
        else:
            sql_agg_col = SumWhen(report_column.field, whens={val: 1}, else_=0, alias=alias)

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


def _get_column_type(data_type):
    if data_type == TYPE_STRING:
        return sqlalchemy.UnicodeText
    return get_column_type(data_type)
