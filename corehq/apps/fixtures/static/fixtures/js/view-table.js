$(function () {
    var data = hqImport('hqwebapp/js/initial_page_data.js').get;
    if (data('renderReportTables')) {
        var options = {};
        _.each([
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
        ], function(name) {
            var value = data(name);
            if (value !== undefined) {
                options[name] = value;
            }
        });
        var reportTables = new HQReportDataTables(options);
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
});
