/* globals hqDefine, hqImport */
hqDefine('hqadmin/js/hqadmin_base_report', function () {
    $(function() {
        var aoColumns = hqImport('hqwebapp/js/initial_page_data').get('aoColumns');
        if (aoColumns) {
            var reportTables = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables({
                aoColumns: aoColumns,
            });
            reportTables.render();
        }
    });
});
