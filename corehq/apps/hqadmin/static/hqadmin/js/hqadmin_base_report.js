hqDefine('hqadmin/js/hqadmin_base_report', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap3/datatables_config',
], function (
    $,
    initialPageData,
    datatablesConfig
) {
    $(function () {
        var aoColumns = initialPageData.get('aoColumns');
        if (aoColumns) {
            var reportTables = datatablesConfig.HQReportDataTables({
                aoColumns: aoColumns,
            });
            reportTables.render();
        }
    });
});
