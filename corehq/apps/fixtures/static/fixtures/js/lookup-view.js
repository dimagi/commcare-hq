define([
    "jquery",
    "knockout",
    "ko.mapping",
    "ko.global_handlers",
    "ko.knockout_bindings",
    "hq.helpers",
    "config.dataTables",
], function(
    $,
    ko
) {
    "use strict";
    var initialPageData = $.parseJSON($("#initial-page-data").text());
    if (initialPageData.renderReportTables) {
        var reportTables = new HQReportDataTables(initialPageData.reportTablesOptions);
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    $('.header-popover').popover({
        trigger: 'hover',
        placement: 'bottom'
    });
});
