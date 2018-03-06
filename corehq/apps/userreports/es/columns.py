from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.es import filters
from corehq.apps.es.aggregations import (
    FilterAggregation, MissingAggregation
)
from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn


class AggColumn(object):
    def __init__(self, ui_alias):
        self.row_key = ui_alias

    def get_value(self, row):
        return row.get(self.row_key, None) if row else None


class UCRExpandEsDatabaseSubcolumn(UCRExpandDatabaseSubcolumn):
    def __init__(self, header, ui_alias, es_alias, expand_value, data_source_field, *args, **kwargs):
        self.ui_alias = ui_alias
        self.data_source_field = data_source_field
        self.es_alias = es_alias
        super(UCRExpandEsDatabaseSubcolumn, self).__init__(
            header, slug=ui_alias, expand_value=expand_value, agg_column=AggColumn(ui_alias), *args, **kwargs
        )

    @property
    def aggregation(self):
        if self.expand_value is None:
            return MissingAggregation(
                self.es_alias, self.data_source_field
            )
        return FilterAggregation(
            self.es_alias, filters.term(self.data_source_field, self.expand_value)
        )

    def get_es_data(self, row):
        return row[self.es_alias]['doc_count']


def expand_column(report_column, distinct_values, lang):
    columns = []
    for index, val in enumerate(distinct_values):
        ui_alias = "{}-{}".format(report_column.column_id, index)
        es_alias = safe_es_column(ui_alias)
        columns.append(UCRExpandEsDatabaseSubcolumn(
            "{}-{}".format(report_column.get_header(lang), val),
            ui_alias=ui_alias,
            es_alias=es_alias,
            expand_value=val,
            data_source_field=report_column.field,
            sortable=False,
            data_slug="{}-{}".format(report_column.column_id, index),
            format_fn=report_column.get_format_fn(),
            help_text=report_column.description
        ))
    return columns


def safe_es_column(column_name):
    return column_name.replace('-', '_dash_')
