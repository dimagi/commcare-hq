(function () {
    var initialPageData = $.parseJSON($("#initial-page-json").text());
    if (initialPageData.renderReportTables) {
        var reportTables = new HQReportDataTables(initialPageData.reportTablesOptions);
        if (typeof standardHQReport !== 'undefined') {
            standardHQReport.handleTabularReportCookies(reportTables);
        }
        reportTables.render();
    }

    $(function() {
        $('.header-popover').popover({
            trigger: 'hover',
            placement: 'bottom'
        });
    });
})();
