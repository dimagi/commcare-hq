The "Report Builder" feature allows users to configure User Configurable Reports through a GUI, instead of writing
the JSON configuration "by hand."


# Design overview

## Populating the front end

### `ManagedReportBuilderDataSourceHelper.data_source_properties`
This dictionary represents the set of all possible form questions or metadata or case
properties that could appear in a report data source.

### `ManagedReportBuilderDataSourceHelper.report_column_options`
This dictionary represents the set of all possible indicators that could appear in a
report. `report_column_options` are mostly derived from `data_source_properties`, but
there are some indicators that can be displayed in a report that don't map directly to
any data source column, such as a "Count" column in an aggregated report, which would
show the number of rows aggregated.

Each data source property yields corresponding report column options through
`DataSourceProperty.to_report_column_option()`

In the report builder front end, report_column_options are used to populate the select
widgets for the report indicators, but data_source_properties are used for configuring
filters.


## Generating the report from user configuration
The configuration created in the browser must be converted to a data source and report
configuration.

### Data Source
The data source indicators are created by mapping the data source property and report
column option ids sent from the browser to the corresponding `DataSourceProperty` and
`ReportColumnOption` objects. We then call `ReportColumnOption.get_indicators()` and
`DataSourceProperty.to_report_filter_indicator()` to get the actual indicator configs

### Report configuration
`ReportColumnOption.to_column_dicts()` returns the column configuration necessary for the
given report column option.
