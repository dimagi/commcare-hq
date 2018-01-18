define([
    "jquery",
    "hqwebapp/js/django",
    "hqwebapp/js/initial_page_data",
    "reports/js/standard_hq_report",
    "reports/js/config.dataTables.bootstrap",
    "reports/js/filters",
    "datatables.fixedColumns",
], function(
    $,
    django,
    initialPageData,
    standardHQReportModule,
    datatablesConfig,
    filters
) {
    if (hqImport(initialPageData).get('renderReportTables')) {
        var reportTables = hqImport(datatablesConfig).HQReportDataTables(hqImport(initialPageData).get('dataTablesOptions')),
            standardHQReport = hqImport(standardHQReportModule).getStandardHQReport();
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    hqImport(filters).init();

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
        });
    });
});
