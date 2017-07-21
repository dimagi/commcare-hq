/* global hqImport, standardHQReport, HQReportDataTables */
$(function () {
    var data = hqImport('hqwebapp/js/initial_page_data.js').get;
    if (data('renderReportTables')) {
        var reportTables = new HQReportDataTables(data('dataTablesOptions')),
            standardHQReport = hqImport("reports/js/standard_hq_report.js").getStandardHQReport();
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
        });
    });
});
