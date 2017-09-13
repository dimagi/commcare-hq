/* globals define */
define("fixtures/js/built", [
    "reports/js/filters",
    "reports/js/standard_hq_report",
    "reports/js/config.dataTables.bootstrap",
], function(
    filters,
    standardHQReportModule,
    datatablesConfig
){
    return {
        filters: filters,
        standardHQReportModule: standardHQReportModule,
        datatablesConfig: datatablesConfig,
    };
});
