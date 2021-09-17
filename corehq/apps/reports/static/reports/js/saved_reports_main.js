hqDefine("reports/js/saved_reports_main", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'reports/js/report_config_models',
    'reports/js/scheduled_reports_list',
    'hqwebapp/js/knockout_bindings.ko', // modal binding
], function (
    $,
    ko,
    initialPageData,
    reportConfigModels,
    scheduledReports,
) {
    $(function () {

        var $configList = $("#ko-report-config-list");
        if ($configList.length) {
            $configList.koApplyBindings(reportConfigModels.reportConfigsViewModel({
                items: initialPageData.get('configs'),
                saveUrl: initialPageData.reverse("add_report_config"),
            }));
        };

        $("#js-scheduled-reports-table").koApplyBindings(scheduledReports.scheduledReportListModel({
            scheduled_reports: initialPageData.get('scheduled_reports'),
            is_admin: initialPageData.get('is_admin'),
            user_email: initialPageData.get('user_email'),
            is_owner: true,
            urls: {
                getPage: initialPageData.reverse("page_context"),
                getPagePage: initialPageData.reverse("reports_home"),
            }
        }));

        $("#js-other-scheduled-reports-table").koApplyBindings(scheduledReports.scheduledReportListModel({
            scheduled_reports: initialPageData.get('others_scheduled_reports'),
            is_admin: initialPageData.get('is_admin'),
            user_email: initialPageData.get('user_email'),
            is_owner: false,
            urls: {
                getPage: initialPageData.reverse("page_context"),
                getPagePage: initialPageData.reverse("reports_home"),
            }
        }));

    });
});
