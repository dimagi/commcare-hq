/* globals COMMCAREHQ_MODULES, standardHQReport */
/*
    Ugly half-measure, because reports and UCR traditionally depend on a global standardHQReport
    variable that's defined in several different places. The UCR version of standardHQReport now
    lives in userreports/js/configurable_report.js, while the non-UCR version lives in this file
    and several custom reports still define standardHQReport as a global var.

    To add to the jankiness of this file, it currently lives in a half-requirejs, half-non-requirejs state.

    This file also controls some basic event handling for report pages, such as the "Apply" button.
*/
hqDefine("reports/js/bootstrap3/standard_hq_report", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'bootstrap',
], function (
    $,
    _,
    initialPageData
) {
    var standardReport = undefined,
        asyncReport = undefined;

    var getStandard = function () {
        if (typeof standardReport !== 'undefined') {
            return standardReport;
        }

        if (typeof standardHQReport !== 'undefined') {
            // Custom reports, notably ewsghana
            standardReport = standardHQReport;
        } else {
            var ucr = "userreports/js/configurable_report";
            // This check doesn't work in a requirejs environment. Part of migrating UCR is going to be updating this.
            if (typeof COMMCAREHQ_MODULES[ucr] !== 'undefined') {
                // UCRs
                standardReport = hqImport(ucr).getStandardHQReport();
            } else {
                hqRequire(["reports/js/bootstrap3/hq_report"], function (hqReportModule) {
                    // Standard reports
                    var reportOptions = _.extend({}, initialPageData.get('js_options'), {
                        emailSuccessMessage: gettext('Report successfully emailed'),
                        emailErrorMessage: gettext('An error occurred emailing your report. Please try again.'),
                    });
                    if (initialPageData.get('startdate')) {
                        reportOptions.datespan = {
                            startdate: initialPageData.get('startdate'),
                            enddate: initialPageData.get('enddate'),
                        };
                    }
                    var standardHQReport = hqReportModule.hqReport(reportOptions);
                    standardHQReport.init();
                    standardReport = standardHQReport;
                });
            }
        }
        return standardReport;
    };

    var getAsync = function () {
        if (typeof asyncReport !== 'undefined') {
            return asyncReport;
        }

        var reportOptions = initialPageData.get('js_options') || {};
        if (reportOptions.slug && reportOptions.async) {
            var asyncHQReport = hqImport("reports/js/bootstrap3/reports.async")({
                standardReport: getStandard(),
            });
            asyncHQReport.init();
            asyncReport = asyncHQReport;
        }

        return asyncReport;
    };

    $(function () {
        // Initialize reports. This must be done inside of a document ready handler
        // so that if this is UCR, userreports/js/configurable_report.js will
        // have been loaded and getStandard will execute the proper branch
        standardReport = getStandard(),
        asyncReport = getAsync();

        $('#apply-btn').on('click', function () {
            $('.hq-generic-report').trigger('apply-click');
        });

        $('[data-toggle="offcanvas"]').click(function () {
            $('.row-offcanvas').toggleClass('active');
        });

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
