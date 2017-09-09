define("fixtures/js/built", [
    "reports/js/filters",
    "reports/js/standard_hq_report",
    "reports/js/config.dataTables.bootstrap",
], function(
    filters,
    standardHQReportModule,
    datatablesConfig
){
    /* in non-development environments, this will be overwritten by r.js */
    return {
        filters: filters,
        standardHQReportModule: standardHQReportModule,
        datatablesConfig: datatablesConfig,
    };
});
