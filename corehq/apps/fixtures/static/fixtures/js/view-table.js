(function () {
    var initialPageData = {};
    _.each($(".initial-page-data"), function(div) {
        var data = $(div).data();
        initialPageData[data.name] = data.value;
    });
    if (initialPageData.renderReportTables) {
        var reportTables = new HQReportDataTables(_.pick(initialPageData, [
            'slug',
            'defaultRows',
            'startAtRowNum',
            'showAllRowsOption',
            'autoWidth',
            'aoColumns',
            'customSort',
            'ajaxSource',
            'ajaxParams',
            'fixColumns',
            'fixColsNumLeft',
            'fixColsWidth',
        ]));
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
