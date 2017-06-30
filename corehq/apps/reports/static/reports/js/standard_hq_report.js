/* globals COMMCAREHQ_MODULES, standardHQReport */
/*
    Ugly half-measure, because reports and UCR traditionally depend on a global standardHQReport
    variable that's defined in several different places. The UCR version of standardHQReport now
    lives in userreports/js/configurable_report.js, whereas the other standardHQReport vars are
    still defined globally. This module's sole purpose is to fetch the correct standardHQReport,
    if it exists at all.
*/
hqDefine("reports/js/standard_hq_report.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
        standardReport = undefined,
        asyncReport = undefined;

    var getStandard = function() {
        if (typeof standardReport !== 'undefined') {
            return standardReport;
        }

        if (typeof standardHQReport !== 'undefined') {
            standardReport = standardHQReport;
        } else {
            var ucr = "userreports/js/configurable_report.js";
            if (typeof COMMCAREHQ_MODULES[ucr] !== 'undefined') {
                standardReport = hqImport(ucr).getStandardHQReport();
            } else {
                var reportOptions = _.extend({}, initial_page_data('js_options'), {
                    emailSuccessMessage: gettext('Report successfully emailed'),
                    emailErrorMessage: gettext('An error occurred emailing you report. Please try again.'),
                });
                if (initial_page_data('startdate')) {
                    reportOptions.datespan = {
                        startdate: initial_page_data('startdate'),
                        enddate: initial_page_data('enddate'),
                    };
                }
                var standardHQReport = new HQReport(reportOptions);
                standardHQReport.init();
                standardReport = standardHQReport;
            }
        }
        return standardReport;
    };

    var getAsync = function() {
        var reportOptions = initial_page_data('js_options');
        if (reportOptions.slug && reportOptions.async) {
            var asyncHQReport = new HQAsyncReport({
                standardReport: getStandard(),
            });
            asyncHQReport.init();
        }
    };

    $(function() {
        $('.report-description-popover').popover({
            placement: 'right',
            trigger: 'hover',
        });
    });

    return {
        getAsyncHQReport: getAsync,
        getStandardHQReport: getStandard,
    };
});
