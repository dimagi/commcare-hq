hqDefine('hqadmin/js/faceted_report', function() {
    var standardHQReport, asyncHQReport;

    $(function() {
        standardHQReport = hqImport("reports/js/standard_hq_report").getStandardHQReport();
        asyncHQReport = hqImport("reports/js/standard_hq_report").getAsyncHQReport();
    });

    return {
        standardHQReport: standardHQReport,
        asyncHQReport: asyncHQReport,
    };
});
