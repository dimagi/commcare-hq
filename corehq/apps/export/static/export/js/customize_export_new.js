hqDefine('export/js/customize_export_new', function() {
var initialPageData = hqImport('hqwebapp/js/initial_page_data');
        $(function () {
            var ExportInstance = hqImport('export/js/models').ExportInstance;
            var customExportView = new ExportInstance(
                initialPageData.get('export_instance|JSON'),
                {
                    saveUrl: initialPageData.get('request.get_full_path|safe|JSON'),
                    hasExcelDashboardAccess: initialPageData.get('has_excel_dashboard_access|JSON'),
                    hasDailySavedAccess: initialPageData.get('has_daily_saved_export_access|JSON'),
                    formatOptions: initialPageData.get('format_options|JSON'),
                    numberOfAppsToProcess: initialPageData.get('number_of_apps_to_process'),
                }
            );
            hqImport('hqwebapp/js/initial_page_data').registerUrl(
                "build_schema", "/a/---/data/export/build_full_schema/"
            )
            $('#customize-export').koApplyBindings(customExportView);
            $('.export-tooltip').tooltip();
        });
});
