/* global hqImport */
$(function () {
    var data = hqImport('hqwebapp/js/initial_page_data').get;
    if (data('renderReportTables')) {
        var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables(data('dataTablesOptions')),
            standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    hqImport("reports/js/filters").init();

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
        });
    });
});
