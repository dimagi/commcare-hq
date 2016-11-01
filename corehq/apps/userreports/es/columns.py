from corehq.apps.es import filters
from corehq.apps.es.aggregations import FilterAggregation
from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn


class UCRExpandEsDatabaseSubcolumn(UCRExpandDatabaseSubcolumn):
    def __init__(self, header, aggregation, es_alias, ui_alias, *args, **kwargs):
        self.aggregation = aggregation
        self.es_alias = es_alias
        self.ui_alias = ui_alias
        super(UCRExpandEsDatabaseSubcolumn, self).__init__(header, *args, **kwargs)


def expand_column(report_column, distinct_values, lang):
    columns = []
    for index, val in enumerate(distinct_values):
        es_alias = u"{}_dash_{}".format(report_column.column_id, index)
        ui_alias = u"{}-{}".format(report_column.column_id, index)
        # todo aggregation only supports # of matches
        columns.append(UCRExpandEsDatabaseSubcolumn(
            u"{}-{}".format(report_column.get_header(lang), val),
            expand_value=val,
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
