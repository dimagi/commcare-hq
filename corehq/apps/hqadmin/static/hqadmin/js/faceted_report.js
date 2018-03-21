hqDefine('hqadmin/js/faceted_report', function() {
    $(function() {
        var hqReport = hqImport("reports/js/standard_hq_report");
        hqReport.getStandardHQReport();
        hqReport.getAsyncHQReport();
    });
});
