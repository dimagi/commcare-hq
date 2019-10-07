from memoized import memoized

from couchexport.export import export_from_tables

from corehq.apps.userreports.columns import get_expanded_column_config
from corehq.apps.userreports.models import get_report_config


def get_expanded_columns(column_configs, data_source_config):
    return {
        column_config.column_id: [
            sql_col.slug for sql_col in get_expanded_column_config(
                data_source_config, column_config, 'en'
            ).columns
        ]
        for column_config in column_configs
        if column_config.type == 'expanded'
    }


def has_location_filter(view_fn, *args, **kwargs):
    """check that the report has at least one location based filter or
    location choice provider filter
    """
    report, _ = get_report_config(config_id=kwargs.get('subreport_slug'), domain=kwargs.get('domain'))
    return any(
        getattr(getattr(filter_, 'choice_provider', None), 'location_safe', False) or
        getattr(filter_, 'location_filter', False)
        for filter_ in report.ui_filters
    )


class ReportExport(object):
    """Export all the rows of a UCR report
    """

    def __init__(self, domain, title, report_config, lang, filter_values):
        self.domain = domain
        self.title = title
        self.report_config = report_config
        self.lang = lang
        self.filter_values = filter_values

    @property
    @memoized
    def data_source(self):
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        data_source = ConfigurableReportDataSource.from_spec(self.report_config, include_prefilters=True)
        data_source.lang = self.lang
        data_source.set_filter_values(self.filter_values)
        data_source.set_order_by([(o['field'], o['order']) for o in self.report_config.sort_expression])
        return data_source

    def create_export(self, file_path, format_):
        """Save this report to a file
        :param file_path: The path to the file the report should be saved
        :param format_: The format of the resulting export
        """
        return export_from_tables(self.get_table(), file_path, format_)

    @memoized
    def get_table(self):
        """Generate a table of all rows of this report
        """
        headers = [
            column.header
            for column in self.data_source.inner_columns if column.data_tables_column.visible
        ]

        column_id_to_expanded_column_ids = get_expanded_columns(
            self.data_source.top_level_columns,
            self.data_source.config
        )
        column_ids = []
        for column in self.report_config.report_columns:
            if column.visible:
                column_ids.extend(column_id_to_expanded_column_ids.get(column.column_id, [column.column_id]))

        rows = [[raw_row[column_id] for column_id in column_ids] for raw_row in self.data_source.get_data()]
        total_rows = [self.data_source.get_total_row()] if self.data_source.has_total_row else []

        export_table = [
            [
                self.title,
                [headers] + rows + total_rows
            ]
        ]

        return export_table
