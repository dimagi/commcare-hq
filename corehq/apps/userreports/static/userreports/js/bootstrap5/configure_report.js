hqDefine('userreports/js/bootstrap5/configure_report', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/multiselect_utils',
    'userreports/js/bootstrap5/report_config',
    'userreports/js/constants',
    'app_manager/js/forms/case_knockout_bindings',
    'hqwebapp/js/bootstrap5/knockout_bindings.ko',      // sortable and sortableList
    'hqwebapp/js/components/inline_edit',
    'hqwebapp/js/components/select_toggle',
    'commcarehq',
], function (
    $,
    initialPageData,
    multiselectUtils,
    reportBuilder,
    constants,
) {
    $(function () {
        var existingReport = initialPageData.get('existing_report'),
            reportDescription = initialPageData.get('report_description');

        var reportConfig = new reportBuilder.reportBuilder.ReportConfig({
            "columnOptions": initialPageData.get('column_options'),
            "initialColumns": initialPageData.get('initial_columns'),
            "app": initialPageData.get('application'),
            "sourceId": initialPageData.get('source_id'),
            "sourceType": initialPageData.get('source_type'),
            "registrySlug": initialPageData.get('registry_slug'),
            "reportPreviewUrl": initialPageData.get('report_preview_url'),
            "previewDatasourceId": initialPageData.get('preview_datasource_id'),
            "existingReport": existingReport ? existingReport._id : null,
            "existingReportType": initialPageData.get('existing_report_type'),
            "reportTitle": initialPageData.get('report_title'),
            "reportDescription": reportDescription ? reportDescription : null,
            "dataSourceProperties": initialPageData.get('data_source_properties'),
            "initialDefaultFilters": initialPageData.get('initial_default_filters'),
            "initialUserFilters": initialPageData.get('initial_user_filters'),
            "initialLocation": initialPageData.get('initial_location'),
            "initialChartType": initialPageData.get('initial_chart_type'),
            "mapboxAccessToken": initialPageData.get('MAPBOX_ACCESS_TOKEN'),
            "dateRangeOptions": initialPageData.get('date_range_options'),
            "formatOptions": constants.FORMAT_OPTIONS,
            "defaultFilterFormatOptions": constants.DEFAULT_FILTER_FORMAT_OPTIONS,
            // In previewMode, report can't be saved.
            "previewMode": (
                !initialPageData.get('has_report_builder_access') ||
                (initialPageData.get('at_report_limit') && !existingReport)),
        });
        $("#reportConfig").koApplyBindings(reportConfig);
        multiselectUtils.createFullMultiselectWidget('domain-selector', {
            selectableHeaderTitle: gettext("Linked projects"),
            selectedHeaderTitle: gettext("Projects to copy to"),
            searchItemTitle: gettext("Search projects"),
        });
        window._bindingsApplied = true;
    });
});
