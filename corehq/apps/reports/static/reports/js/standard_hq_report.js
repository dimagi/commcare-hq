/* globals COMMCAREHQ_MODULES, standardHQReport */
/*
    Ugly half-measure, because reports and UCR traditionally depend on a global standardHQReport
    variable that's defined in several different places. The UCR version of standardHQReport now
    lives in userreports/js/configurable_report.js, whereas the other standardHQReport vars are
    still defined globally. This module's sole purpose is to fetch the correct standardHQReport,
    if it exists at all.
*/
hqDefine("reports/js/standard_hq_report.js", function() {
    var get = function() {
        if (typeof standardHQReport !== 'undefined') {
            return standardHQReport;
        }
        var ucr = "userreports/js/configurable_report.js";
        if (typeof COMMCAREHQ_MODULES[ucr] !== 'undefined') {
            return hqImport(ucr).getStandardHQReport();
        }
        return undefined;
    };

    return {
        getStandardHQReport: get,
    };
});
