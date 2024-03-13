hqDefine("reports/js/saved_reports_main", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'reports/js/report_config_models',
    'reports/js/scheduled_reports_list',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // modal binding
], function (
    $,
    ko,
    initialPageData,
    reportConfigModels,
    scheduledReports
) {
    $(function () {

        var $configList = $("#ko-report-config-list");
        if ($configList.length) {
            $configList.koApplyBindings(reportConfigModels.reportConfigsViewModel({
                items: initialPageData.get('configs'),
                sharedItems: initialPageData.get('shared_saved_reports'),
                saveUrl: initialPageData.reverse("add_report_config"),
            }));
        }

        $("#js-scheduled_reports").koApplyBindings(scheduledReports.scheduledReportListModel({
            scheduled_reports: initialPageData.get('scheduled_reports'),
            other_scheduled_reports: initialPageData.get('others_scheduled_reports'),
            is_admin: initialPageData.get('is_admin'),
        }));
    });
});
