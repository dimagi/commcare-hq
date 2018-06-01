hqDefine('export/js/customize_export_old', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    $(function () {
        var translations = {
            forms: gettext('Forms'),
            repeat: gettext('Repeat: '),
            cases: gettext('Cases'),
            case_history: gettext('Case History'),
            history_to_parents: gettext('Case History > Parent Cases'),
            parent_cases: gettext('Parent Cases'),
        };
        var customExportView = hqImport("export/js/customize_export").CustomExportView.wrap({
            export_type: initialPageData.get('custom_export_type'),
            custom_export: initialPageData.get('custom_export'),
            table_configuration: initialPageData.get('table_configuration'),
            presave: initialPageData.get('presave'),
            export_stock: initialPageData.get('export_stock'),
            deid_options: initialPageData.get('deid_options'),
            column_type_options: initialPageData.get('column_type_options'),
            urls: {
                save: initialPageData.get('request_get_full_path'),
            },
            allow_repeats: initialPageData.get('helper_allow_repeats'),
            default_order: initialPageData.get('default_order'),
            minimal: initialPageData.get('minimal'),
        }, translations, initialPageData.get('has_excel_dashboard_access'));

        var $export = $('#customize-export');
        $export.koApplyBindings(customExportView);

        $export.find('form').on("change input", function() {
            if (customExportView.custom_export.type() === 'form') {
                window.onbeforeunload = function() {
                    var state = customExportView.save.state();
                    if (state !== 'saving' && state !== 'saving-preview' && state !== 'canceling') {
                        return gettext("You have unsaved changes");
                    }
                };
            }
        });

        if (initialPageData("custom_export_id")) {
            $('#delete-export-modal-' + initialPageData("custom_export_id")).find('form').submit(function() {
                window.onbeforeunload = undefined;
            });
        }
    });
});
