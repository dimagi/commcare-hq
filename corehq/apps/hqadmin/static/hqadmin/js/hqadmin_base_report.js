/* globals hqDefine */
hqDefine('hqadmin/js/hqadmin_base_report.js', function () {
    $(function() {
        var aoColumns = hqImport('hqwebapp/js/initial_page_data.js').get('aoColumns');
        if (aoColumns) {
            var reportTables = new HQReportDataTables({
                aoColumns: aoColumns,
            });
            reportTables.render();
        }
    });
});
