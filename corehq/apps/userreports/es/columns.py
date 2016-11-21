from corehq.apps.es import filters
from corehq.apps.es.aggregations import (
    FilterAggregation, SumAggregation, MissingAggregation
)
from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn


class UCRExpandEsDatabaseSubcolumn(UCRExpandDatabaseSubcolumn):
    def __init__(self, header, aggregation, ui_alias, *args, **kwargs):
        self.aggregation = aggregation
        self.ui_alias = ui_alias
        super(UCRExpandEsDatabaseSubcolumn, self).__init__(header, slug=ui_alias, *args, **kwargs)


class FilterAggregationColumn(object):
    _aggregation = FilterAggregation

    def __init__(self, report_column, value, es_alias=None):
        self.report_column = report_column
        self.value = value
        self.es_alias = es_alias or report_column.column_id

    @property
    def aggregation(self):
        return self._aggregation(
            self.es_alias, filters.term(self.report_column.field, self.value)
        )

    def get_data(self, row):
        return row[self.es_alias]['doc_count']


class SumAggregationColumn(FilterAggregationColumn):
    _aggregation = SumAggregation

    @property
    def aggregation(self):
        return self._aggregation(
            self.es_alias, self.report_column.field
        )


class MissingAggregationColumn(SumAggregationColumn):
    _aggregation = MissingAggregation


def expand_column(report_column, distinct_values, lang):
    columns = []
    for index, val in enumerate(distinct_values):
        es_alias = u"{}_dash_{}".format(report_column.column_id, index)
        ui_alias = u"{}-{}".format(report_column.column_id, index)
        if val is None:
            aggregation = MissingAggregationColumn(report_column, val, es_alias)
        else:
            aggregation = FilterAggregationColumn(report_column, val, es_alias)
        # todo aggregation only supports # of matches
        columns.append(UCRExpandEsDatabaseSubcolumn(
            u"{}-{}".format(report_column.get_header(lang), val),
            expand_value=val,
            aggregation=aggregation,
            ui_alias=ui_alias,
            sortable=False,
            data_slug=u"{}-{}".format(report_column.column_id, index),
            format_fn=report_column.get_format_fn(),
            help_text=report_column.description
        ))
    return columns
