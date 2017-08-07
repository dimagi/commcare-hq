/* global hqImport */
$(function () {
    var data = hqImport('hqwebapp/js/initial_page_data.js').get;
    if (data('renderReportTables')) {
        var reportTables = hqImport("reports/js/config.dataTables.bootstrap.js").HQReportDataTables(data('dataTablesOptions')),
            standardHQReport = hqImport("reports/js/standard_hq_report.js").getStandardHQReport();
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    hqImport("reports/js/filters.js").init();

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
        });
    });
});
