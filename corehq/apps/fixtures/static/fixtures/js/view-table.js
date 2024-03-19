hqDefine("fixtures/js/view-table", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "reports/js/standard_hq_report",
    "reports/js/config.dataTables.bootstrap",
    "reports/js/filters/main",
    "datatables.fixedColumns",
], function (
    $,
    initialPageData,
    standardHQReportModule,
    datatablesConfig,
    filters
) {
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
});
