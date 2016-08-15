/* global define, standardHQReport */
/**
 *  Handles fixtures' "View Table" page.
 */
define([
    "jquery",
    "reports/javascripts/filters",
    "reports/javascripts/config.dataTables.bootstrap",
    "style/js/hq.helpers",
], function(
    $,
    filters,
    datatablesConfig
) {
    "use strict";
    filters.init();
    var initialPageData = $.parseJSON($("#initial-page-json").text());
    if (initialPageData.renderReportTables) {
        var reportTables = new datatablesConfig.HQReportDataTables(initialPageData.reportTablesOptions);
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    $('.header-popover').popover({
        trigger: 'hover',
        placement: 'bottom',
    });
});
