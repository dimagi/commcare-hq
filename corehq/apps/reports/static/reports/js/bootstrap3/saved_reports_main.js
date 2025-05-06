import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import reportConfigModels from "reports/js/bootstrap3/report_config_models";
import scheduledReports from "reports/js/scheduled_reports_list";
import "hqwebapp/js/bootstrap3/knockout_bindings.ko";  // modal binding
import "hqwebapp/js/components/pagination";

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
