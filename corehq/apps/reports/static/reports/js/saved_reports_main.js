hqDefine("reports/js/saved_reports_main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'reports/js/saved_reports',
], function(
    $,
    initialPageData,
    reportConfigModels,
) {
    $(function() {
        var $configList = $("#ko-report-config-list");
        if ($configList.length) {
            $configList.koApplyBindings(new reportConfigModels.ReportConfigsViewModel({
                items: initialPageData.get('configs'),
                saveUrl: initialPageData.reverse("add_report_config"),
            }));
        }
    });
});
