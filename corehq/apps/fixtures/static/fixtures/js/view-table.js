/* global define */
define([
    "jquery",
    "hqwebapp/js/django",
    "hqwebapp/js/initial_page_data",
    "reports/js/filters",
    "reports/js/standard_hq_report",
    "reports/js/config.dataTables.bootstrap",
    "hqwebapp/js/hq.helpers",
], function(
    $,
    django,
    initialPageData,
    filters,
    standardHQReportModule,
    datatablesConfig
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

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
        });
    });
});
