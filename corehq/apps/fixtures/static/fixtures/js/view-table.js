/* global define */
define([
    "jquery",
    "hqwebapp/js/django",
    "hqwebapp/js/initial_page_data",
    "fixtures/js/built",
], function(
    $,
    django,
    initialPageData,
    fixtures
) {
    if (initialPageData.get('renderReportTables')) {
        var reportTables = fixtures.datatablesConfig.HQReportDataTables(initialPageData.get('dataTablesOptions')),
            standardHQReport = fixtures.standardHQReportModule.getStandardHQReport();
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    fixtures.filters.init();

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom',
        });
    });
});
