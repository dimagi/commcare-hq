hqDefine('export/js/customize_export_new', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'export/js/models',
    'hqwebapp/js/toggles',
], function (
    $,
    ko,
    initialPageData,
    models,
    toggles,
) {
    $(function () {
        var customExportView = new models.ExportInstance(
            initialPageData.get('export_instance'),
            {
                saveUrl: initialPageData.get('full_path'),
                hasExcelDashboardAccess: initialPageData.get('has_excel_dashboard_access'),
                hasDailySavedAccess: initialPageData.get('has_daily_saved_export_access'),
                formatOptions: initialPageData.get('format_options'),
                sharingOptions: initialPageData.get('sharing_options'),
                hasOtherOwner: initialPageData.get('has_other_owner'),
                numberOfAppsToProcess: initialPageData.get('number_of_apps_to_process'),
            }
        );
        initialPageData.registerUrl(
            "build_schema", "/a/---/data/export/build_full_schema/"
        );
        $('#customize-export').koApplyBindings(customExportView);
        $('.export-tooltip').tooltip();

        // check feature flag here
        if (toggles.toggleEnabled('SUPPORT_GEO_JSON_EXPORT')) {
            var exportTable = initialPageData.get('export_instance').tables.find(function(table) {
                return table.doc_type && table.doc_type == "TableConfiguration";
            });

            var geoSelectElement = $('#geo-property-select');
            $.each(exportTable.columns, function(index, column) {
                geoSelectElement.append('<option value="' + column.label + '">' + column.label + '</option>');
            });

            $('#format-select').change(function () {
                const selectedValue = $(this).val();
                if (selectedValue == "geojson") {
                    $("#select-geo-property").show();
                } else {
                    $("#select-geo-property").hide();
                }
            });
        }
    });
});
