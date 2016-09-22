from django.utils.translation import ugettext as _

from corehq.apps.es import filters
from corehq.apps.es.aggregations import FilterAggregation
from corehq.apps.reports.datatables import DataTablesColumn

from corehq.apps.userreports.const import DEFAULT_MAXIMUM_EXPANSION


class EsColumnConfig(object):
    """
    Stub object to send column information to the data source
    """

    def __init__(self, columns, headers=None, warnings=None):
        self.columns = columns
        if headers is not None:
            self.headers = [c.header for c in self.columns]
        else:
            self.headers = headers
        self.warnings = warnings if warnings is not None else []


class EsColumn(object):
    def __init__(self, header, format_fn=None, *args, **kwargs):
        self.header = header
        self.format_fn = format_fn
        self.data_tables_column = DataTablesColumn(header, *args, **kwargs)


class UCRExpandDatabaseSubcolumn(EsColumn):
    def __init__(self, header, aggregation, es_alias, ui_alias, format_fn=None, *args, **kwargs):
        self.aggregation = aggregation
        self.es_alias = es_alias
        self.ui_alias = ui_alias
        super(UCRExpandDatabaseSubcolumn, self).__init__(
            header, format_fn=None, *args, **kwargs
        )


def get_expanded_es_column_config(data_source_configuration, column_config, lang):
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
    vals, over_expansion_limit = _get_distinct_values(
        data_source_configuration, column_config, column_config.max_expansion
    )

    if over_expansion_limit:
        column_warnings.append(_(
            u'The "{header}" column had too many values to expand! '
            u'Expansion limited to {max} distinct values.'
        ).format(
            header=column_config.get_header(lang),
            max=column_config.max_expansion,
        ))
    return EsColumnConfig(_expand_column(column_config, vals, lang), warnings=column_warnings)


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
    from corehq.apps.userreports.es.adapter import IndicatorESAdapter
    adapter = IndicatorESAdapter(data_source_configuration)
    query = adapter.get_query_object()
    too_many_values = False

    distinct_values = query.distinct_values(column_config.field, expansion_limit)
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
        es_alias = u"{}_dash_{}".format(report_column.column_id, index)
        ui_alias = u"{}-{}".format(report_column.column_id, index)
        # todo aggregation only supports # of matches
        columns.append(UCRExpandDatabaseSubcolumn(
            u"{}-{}".format(report_column.get_header(lang), val),
            aggregation=FilterAggregation(
                es_alias, filters.term(report_column.field, val)
            ),
            es_alias=es_alias,
            ui_alias=ui_alias,
            sortable=False,
            data_slug=u"{}-{}".format(report_column.column_id, index),
            format_fn=report_column.get_format_fn(),
            help_text=report_column.description
        ))
    return columns
