import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import standardHQReportModule from "reports/js/bootstrap3/standard_hq_report";
import datatablesConfig from "reports/js/bootstrap3/datatables_config";
import filters from "reports/js/filters/bootstrap3/main";
import "datatables.fixedColumns";

if (initialPageData.get('renderReportTables')) {
    var reportTables = datatablesConfig.HQReportDataTables(initialPageData.get('dataTablesOptions')),
        standardHQReport = standardHQReportModule.getStandardHQReport();
    if (typeof standardHQReport !== 'undefined') {
        standardHQReport.handleTabularReportCookies(reportTables);
    }
    reportTables.render();
}

filters.init();

$(function () {
    $('.header-popover').popover({
        trigger: 'hover',
        placement: 'bottom',
    });
});
