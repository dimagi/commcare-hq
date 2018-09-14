hqDefine('userreports/js/configure_report', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data'),
        reportBuilder = hqImport('userreports/js/report_config').reportBuilder;

    $(function () {
        var existing_report = initialPageData.get('existing_report'),
            report_description = initialPageData.get('report_description');

        var reportConfig = new reportBuilder.ReportConfig({
            "columnOptions": initialPageData.get('column_options'),
            "initialColumns": initialPageData.get('initial_columns'),
            "app": initialPageData.get('application'),
            "sourceId": initialPageData.get('source_id'),
            "sourceType": initialPageData.get('source_type'),
            "reportPreviewUrl": initialPageData.get('report_preview_url'),
            "previewDatasourceId": initialPageData.get('preview_datasource_id'),
            "existingReport": existing_report ? existing_report._id : null,
            "existingReportType": initialPageData.get('existing_report_type'),
            "reportTitle": initialPageData.get('report_title'),
            "reportDescription": report_description ? report_description : null,
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
                (initialPageData.get('at_report_limit') && !existing_report)),
        });
        $("#reportConfig").koApplyBindings(reportConfig);
        window._bindingsApplied = true;
    });
});
