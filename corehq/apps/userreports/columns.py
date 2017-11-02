from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext as _

from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.userreports.const import (
    DEFAULT_MAXIMUM_EXPANSION,
    UCR_ES_BACKEND,
    UCR_SQL_BACKEND,
)
from corehq.apps.userreports.exceptions import ColumnNotFoundError
from corehq.apps.userreports.util import get_indicator_adapter, get_backend_id
import six


class UCRExpandDatabaseSubcolumn(DatabaseColumn):
    """
    A light wrapper around DatabaseColumn that stores the expand value that this DatabaseColumn is based on.
    """
    def __init__(self, header, agg_column=None, expand_value=None, *args, **kwargs):
        self.expand_value = expand_value
        super(UCRExpandDatabaseSubcolumn, self).__init__(
            header, agg_column, *args, **kwargs
        )


class ColumnConfig(object):
    """
    Stub object to send column information to the data source
    """

    def __init__(self, columns, warnings=None):
        self.columns = columns
        self.headers = [c.header for c in self.columns]
        self.warnings = warnings if warnings is not None else []


def get_distinct_values(data_source_configuration, column_config, expansion_limit=DEFAULT_MAXIMUM_EXPANSION):
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
    adapter = get_indicator_adapter(data_source_configuration)
    return adapter.get_distinct_values(column_config.field, expansion_limit)


def get_expanded_column_config(data_source_configuration, column_config, lang):
    """
    Given an ExpandedColumn, return a list of Column-like objects. Each column
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
        vals, over_expansion_limit = get_distinct_values(
            data_source_configuration, column_config, column_config.max_expansion
        )
    except ColumnNotFoundError as e:
        return ColumnConfig([], warnings=[six.text_type(e)])

    if over_expansion_limit:
        column_warnings.append(_(
            'The "{header}" column had too many values to expand! '
            'Expansion limited to {max} distinct values.'
        ).format(
            header=column_config.get_header(lang),
            max=column_config.max_expansion,
        ))

    column = _get_expanded_column(data_source_configuration, column_config, vals, lang)

    return ColumnConfig(column, warnings=column_warnings)


def _get_expanded_column(data_source_config, report_column, values, lang):
    """
    Given an ExpandedColumn, return a list of Column-like objects. Each column
    is configured to show the number of occurrences of one of the given distinct_values.

    :param report_column:
    :param distinct_values:
    :return:
    """
    from corehq.apps.userreports.sql.columns import expand_column as sql_expand_column
    from corehq.apps.userreports.es.columns import expand_column as es_expand_column
    backend_id = get_backend_id(data_source_config)
    if backend_id == UCR_ES_BACKEND:
        fn = es_expand_column
    else:
        fn = sql_expand_column
    return fn(report_column, values, lang)
