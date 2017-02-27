$(function() {
    var aoColumns = hqImport('hqwebapp/js/initial_page_data.js').get('aoColumns');
    if (aoColumns) {
        var reportTables = new HQReportDataTables({
            aoColumns: aoColumns,
        });
        reportTables.render();
    }
});
