hqDefine('export/js/customize_export_old', function() {
        $(function () {
            var translations = {
                forms: "{% trans 'Forms'|escapejs %}",
                repeat: "{% trans 'Repeat: '|escapejs %}",
                cases: "{% trans 'Cases'|escapejs %}",
                case_history: "{% trans 'Case History'|escapejs %}",
                history_to_parents: "{% trans 'Case History > Parent Cases'|escapejs %}",
                parent_cases: "{% trans 'Parent Cases'|escapejs %}"
            };
            var customExportView = CustomExportView.wrap({
                export_type: {{ custom_export.type|JSON }},
                custom_export: {{ custom_export|JSON }},
                table_configuration: {{ table_configuration|JSON }},
                presave: {{ presave|JSON }},
                export_stock: {{ export_stock|JSON }},
                deid_options: {{ deid_options|JSON }},
                column_type_options: {{ column_type_options|JSON }},
                urls: {
                    save: {{ request.get_full_path|safe|JSON }}
                },
                allow_repeats: {{ helper.allow_repeats|JSON }},
                default_order: {{ default_order|JSON }},
                minimal: {{ minimal|JSON }}
            }, translations, {{ has_excel_dashboard_access|JSON }});

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
