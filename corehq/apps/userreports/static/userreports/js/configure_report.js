hqDefine('userreports/js/configure_report', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
        multiselectUtils = hqImport('hqwebapp/js/multiselect_utils'),
        reportBuilder = hqImport('userreports/js/report_config').reportBuilder;

    $(function () {
        var existingReport = initialPageData.get('existing_report'),
            reportDescription = initialPageData.get('report_description');

        var reportConfig = new reportBuilder.ReportConfig({
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
