hqDefine('export/js/customize_export_old', function() {
var initialPageData = hqImport('hqwebapp/js/initial_page_data');
        $(function () {
            var translations = {
                forms: gettext('Forms'|escapejs),
                repeat: gettext('Repeat: '|escapejs),
                cases: gettext('Cases'|escapejs),
                case_history: gettext('Case History'|escapejs),
                history_to_parents: gettext('Case History > Parent Cases'|escapejs),
                parent_cases: gettext('Parent Cases'|escapejs)
            };
            var customExportView = CustomExportView.wrap({
                export_type: initialPageData.get('custom_export.type|JSON'),
                custom_export: initialPageData.get('custom_export|JSON'),
                table_configuration: initialPageData.get('table_configuration|JSON'),
                presave: initialPageData.get('presave|JSON'),
                export_stock: initialPageData.get('export_stock|JSON'),
                deid_options: initialPageData.get('deid_options|JSON'),
                column_type_options: initialPageData.get('column_type_options|JSON'),
                urls: {
                    save: initialPageData.get('request.get_full_path|safe|JSON')
                },
                allow_repeats: initialPageData.get('helper.allow_repeats|JSON'),
                default_order: initialPageData.get('default_order|JSON'),
                minimal: initialPageData.get('minimal|JSON')
            }, translations, initialPageData.get('has_excel_dashboard_access|JSON'));

            var $export = $('#customize-export');
            $export.koApplyBindings(customExportView);

            $export.find('form').on("change input", function() {
                if (customExportView.custom_export.type() === 'form') {
                    window.onbeforeunload = function() {
                        var state = customExportView.save.state();
                        if (state !== 'saving' && state !== 'saving-preview' && state !== 'canceling') {
                           return gettext("You have unsaved changes");
                        }
                    }
                }
            });
        });
});
