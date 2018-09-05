hqDefine("reports/js/saved_reports_main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'reports/js/report_config_models',
    'hqwebapp/js/knockout_bindings.ko', // modal binding
], function(
    $,
    initialPageData,
    reportConfigModels
) {
    $(function() {
        var $configList = $("#ko-report-config-list");
        if ($configList.length) {
            $configList.koApplyBindings(reportConfigModels.reportConfigsViewModel({
                items: initialPageData.get('configs'),
                saveUrl: initialPageData.reverse("add_report_config"),
            }));
        }
    });
});
