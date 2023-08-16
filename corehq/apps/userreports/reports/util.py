from memoized import memoized

from corehq import toggles
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


def report_has_location_filter(config_id, domain):
    """check that the report has at least one location based filter or
    location choice provider filter
    """
    if not (config_id and domain):
        return False
    report, _ = get_report_config(config_id=config_id, domain=domain)
    return any(
        getattr(getattr(filter_, 'choice_provider', None), 'location_safe', False) or
        getattr(filter_, 'location_filter', False)
        for filter_ in report.ui_filters
    )


class ReportExport(object):
    """Export all the rows of a UCR report
    """

    def __init__(self, domain, title, report_config, lang, filter_values, request_user=None):
        self.domain = domain
        self.title = title
        self.report_config = report_config
        self.lang = lang
        self.filter_values = filter_values
        self.request_user = request_user

    @property
    def data_source(self):
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        data_source = ConfigurableReportDataSource.from_spec(self.report_config, include_prefilters=True)
        data_source.lang = self.lang

        '''
        Removing location from the filters for the locations that are not applicable for the current user.
        Example filters
        {'closed_0bbbc4e4_string_0': [Choice(value='_all', display='_all')], 'computed_owner_name_40cc88a0_1': [Choice(value='_all', display='_all')], \
        'computed_owner_location_with_descendants_b5e07138_2': [Choice(value='30e822c671e1405ab0882bd47776c632', display='Agra [City]'), \
                                                                Choice(value='b16528558c9e48debcf9e3a0cb65c009', display='b16528558c9e48debcf9e3a0cb65c009), \
                                                                Choice(value='4cee79947b41403981882dda5fb46310', display='Noida [City]')]}

        In this scenario valid location filters for the user are Agra [City] and Noida [City], which can be identified by their display and value content.
        '''
        if toggles.LOCATION_RESTRICTED_SCHEDULED_REPORTS.enabled(self.domain):
            location_key = None
            user_location_ids = self.request_user.get_location_ids(self.domain)
            user_filtered_locations = []
            for k, v in self.filter_values.items():
                if 'computed_owner_location' in k:
                    location_key = k
                    user_filtered_locations = [choice for choice in v if choice.value in user_location_ids]
            if location_key:
                self.filter_values[location_key] = user_filtered_locations

        data_source.set_filter_values(self.filter_values)
        data_source.set_order_by([(o['field'], o['order']) for o in self.report_config.sort_expression])
        return data_source

    def create_export(self, file_path, format_):
        """Save this report to a file
        :param file_path: The path to the file the report should be saved
        :param format_: The format of the resulting export
        """
        return export_from_tables(self.get_table(), file_path, format_)

    @property
    def header_rows(self):
        return [[
            column.header
            for column in self.data_source.inner_columns if column.data_tables_column.visible
        ]]

    def get_data(self):
        return list(self.data_source.get_data())

    @property
    @memoized
    def total_rows(self):
        return [self.data_source.get_total_row()] if self.data_source.has_total_row else []

    @property
    @memoized
    def data_rows(self):
        column_id_to_expanded_column_ids = get_expanded_columns(
            self.data_source.top_level_columns,
            self.data_source.config
        )
        column_ids = []
        for column in self.report_config.report_columns:
            if column.visible:
                column_ids.extend(column_id_to_expanded_column_ids.get(column.column_id, [column.column_id]))

        return [[raw_row[column_id] for column_id in column_ids] for raw_row in self.get_data()]

    def get_table_data(self):
        return self.header_rows + self.data_rows + self.total_rows

    @memoized
    def get_table(self):
        """Generate a table of all rows of this report
        """
        export_table = [
            [
                self.title,
                self.get_table_data()
            ]
        ]

        return export_table
