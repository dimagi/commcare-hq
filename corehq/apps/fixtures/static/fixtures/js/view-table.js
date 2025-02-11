hqDefine("fixtures/js/view-table", [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "reports/js/bootstrap3/standard_hq_report",
    "reports/js/bootstrap3/datatables_config",
    "reports/js/filters/bootstrap3/main",
    "datatables.fixedColumns",
    "commcarehq",
], function (
    $,
    initialPageData,
    standardHQReportModule,
    datatablesConfig,
    filters,
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
