hqDefine('export/js/customize_export_new', function() {
        $(function () {
            var ExportInstance = hqImport('export/js/models').ExportInstance;
            var customExportView = new ExportInstance(
                {{ export_instance|JSON }},
                {
                    saveUrl: {{ request.get_full_path|safe|JSON }},
                    hasExcelDashboardAccess: {{ has_excel_dashboard_access|JSON }},
                    hasDailySavedAccess: {{ has_daily_saved_export_access|JSON }},
                    formatOptions: {{ format_options|JSON }},
                    numberOfAppsToProcess: {{ number_of_apps_to_process }},
                }
            );
            hqImport('hqwebapp/js/initial_page_data').registerUrl(
                "build_schema", "/a/---/data/export/build_full_schema/"
            )
            $('#customize-export').koApplyBindings(customExportView);
            $('.export-tooltip').tooltip();
        });
});
