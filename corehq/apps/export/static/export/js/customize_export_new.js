hqDefine('export/js/customize_export_new', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    $(function () {
        var ExportInstance = hqImport('export/js/models').ExportInstance;
        var customExportView = new ExportInstance(
            initialPageData.get('export_instance'),
            {
                saveUrl: initialPageData.get('full_path'),
                hasExcelDashboardAccess: initialPageData.get('has_excel_dashboard_access'),
                hasDailySavedAccess: initialPageData.get('has_daily_saved_export_access'),
                formatOptions: initialPageData.get('format_options'),
                sharingOptions: initialPageData.get('sharing_options'),
                numberOfAppsToProcess: initialPageData.get('number_of_apps_to_process'),
            }
        );
        initialPageData.registerUrl(
            "build_schema", "/a/---/data/export/build_full_schema/"
        );
        $('#customize-export').koApplyBindings(customExportView);
        $('.export-tooltip').tooltip();
    });
});
