The "Report Builder" feature allows users to configure User Configurable Reports through a GUI, instead of writing
the JSON configuration "by hand."


# Release Plan

The "New Report Builder", or v2 of the report builder resides under a feature flag at the time of writing this
document. [This](http://manage.dimagi.com/default.asp?251977) fogbugz case tracks remaining QA problems that need
fixing before v2 can be released.

When we are ready to transition all projects to the new report builder, follow these steps:
- Remove the REPORT_BUILDER_V2 flag and references to it
- Remove v1 report builder files
    - `corehq/apps/userreports/v1/`
    - `corehq/apps/userreports/reports/builder/v1/`
    - `corehq/apps/userreports/static/userreports/v1/`
    - `corehq/apps/userreports/static/userreports/js/v1/`
    - `corehq/apps/userreports/templates/userreports/v1/`
    - `corehq/apps/userreports/templates/userreports/partials/v1/`
    - `corehq/apps/userreports/templates/userreports/reportbuilder/v1/`
- Remove v1 urls
- Remove v1/v2 diff tests (`test_report_builder_v2_diffs.py`) and the diff files
  (`corehq/apps/userreports/tests/data/report_builder_v2_diffs`)
- Remove `build_report_builder_v2_diffs` management command


# Design overview

## Populating the front end

### `DataSourceBuilder.data_source_properties`
This dictionary represents the set of all possible form questions or metadata or case
properties that could appear in a report data source.

### `DataSourceBuilder.report_column_options`
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
