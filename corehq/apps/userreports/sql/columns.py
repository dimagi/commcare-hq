import sqlalchemy
from sqlagg import SumWhen
from django.utils.translation import ugettext as _
from corehq.apps.userreports.exceptions import ColumnNotFoundError
from corehq.apps.reports.sqlreport import DatabaseColumn
from fluff import TYPE_STRING
from fluff.util import get_column_type


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


def column_to_sql(column):
    # we have to explicitly truncate the column IDs otherwise postgres will do it
    # and will choke on them if there are duplicates: http://manage.dimagi.com/default.asp?175495
    return sqlalchemy.Column(
        column.database_column_name,
        _get_column_type(column.datatype),
        nullable=column.is_nullable,
        primary_key=column.is_primary_key,
    )


def get_expanded_column_config(data_source_configuration, column_config, lang):
    """
    Given an ExpandedColumn, return a list of DatabaseColumn objects. Each DatabaseColumn
    is configured to show the number of occurrences of one of the values present for
    the ExpandedColumn's field.

    This function also adds warnings to the column_warnings parameter.

    :param data_source_configuration:
    :param column_config:
    :param column_warnings:
    :return:
    """
    column_warnings = []
    try:
        vals, over_expansion_limit = _get_distinct_values(
            data_source_configuration, column_config, column_config.max_expansion
        )
    except ColumnNotFoundError as e:
        return SqlColumnConfig([], warnings=[unicode(e)])
    else:
        if over_expansion_limit:
            column_warnings.append(_(
                u'The "{header}" column had too many values to expand! '
                u'Expansion limited to {max} distinct values.'
            ).format(
                header=column_config.get_header(lang),
                max=column_config.max_expansion,
            ))
        return SqlColumnConfig(_expand_column(column_config, vals, lang), warnings=column_warnings)


DEFAULT_MAXIMUM_EXPANSION = 10


def _get_distinct_values(data_source_configuration, column_config, expansion_limit=DEFAULT_MAXIMUM_EXPANSION):
    """
    Return a tuple. The first item is a list of distinct values in the given
    ExpandedColumn no longer than expansion_limit. The second is a boolean which
    is True if the number of distinct values in the column is greater than the
    limit.

    :param data_source_configuration:
    :param column_config:
    :param expansion_limit:
    :return:
    """
    from corehq.apps.userreports.sql import IndicatorSqlAdapter
    adapter = IndicatorSqlAdapter(data_source_configuration)
    too_many_values = False

    table = adapter.get_table()
    if not table.exists(bind=adapter.engine):
        return [], False

    if column_config.field not in table.c:
        raise ColumnNotFoundError(_(
            'The column "{}" does not exist in the report source! '
            'Please double check your report configuration.').format(column_config.field)
        )
    column = table.c[column_config.field]

    query = adapter.session_helper.Session.query(column).limit(expansion_limit + 1).distinct()
    result = query.all()
    distinct_values = [x[0] for x in result]
    if len(distinct_values) > expansion_limit:
        distinct_values = distinct_values[:expansion_limit]
        too_many_values = True

    return distinct_values, too_many_values


def _expand_column(report_column, distinct_values, lang):
    """
    Given an ExpandedColumn, return a list of DatabaseColumn objects. Each column
    is configured to show the number of occurrences of one of the given distinct_values.

    :param report_column:
    :param distinct_values:
    :return:
    """
    columns = []
    for index, val in enumerate(distinct_values):
        alias = u"{}-{}".format(report_column.column_id, index)
        if val is None:
            sql_agg_col = SumWhen(
                whens={"{} is NULL".format(report_column.field): 1}, else_=0, alias=alias
            )
        else:
            sql_agg_col = SumWhen(report_column.field, whens={val: 1}, else_=0, alias=alias)

        columns.append(DatabaseColumn(
            u"{}-{}".format(report_column.get_header(lang), val),
            sql_agg_col,
            sortable=False,
            data_slug=u"{}-{}".format(report_column.column_id, index),
            format_fn=report_column.get_format_fn(),
            help_text=report_column.description
        ))
    return columns


def _get_column_type(data_type):
    if data_type == TYPE_STRING:
        return sqlalchemy.UnicodeText
    return get_column_type(data_type)
