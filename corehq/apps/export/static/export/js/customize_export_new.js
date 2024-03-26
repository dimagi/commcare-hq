hqDefine('export/js/customize_export_new', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'export/js/models',
    'hqwebapp/js/toggles',
    'export/js/const',
], function (
    $,
    ko,
    initialPageData,
    models,
    toggles,
    constants
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
                geoProperties: initialPageData.get('geo_properties'),
            }
        );
        initialPageData.registerUrl(
            "build_schema", "/a/---/data/export/build_full_schema/"
        );
        $('#customize-export').koApplyBindings(customExportView);
        $('.export-tooltip').tooltip();

        if (toggles.toggleEnabled('SUPPORT_GEO_JSON_EXPORT')) {
            const exportFormat = initialPageData.get('export_instance').export_format;
            if (exportFormat === constants.EXPORT_FORMATS.GEOJSON) {
                $("#select-geo-property").show();
                $("#split-multiselects-checkbox-div").hide();
            }

            $('#format-select').change(function () {
                const selectedValue = $(this).val();
                if (selectedValue === constants.EXPORT_FORMATS.GEOJSON) {
                    $("#select-geo-property").show();
                    $("#split-multiselects-checkbox-div").hide();
                } else {
                    $("#select-geo-property").hide();
                    $("#split-multiselects-checkbox-div").show();
                }
            });
        }
    });
});
