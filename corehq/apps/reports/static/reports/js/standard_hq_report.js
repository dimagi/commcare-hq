/* globals COMMCAREHQ_MODULES, HQReport, HQAsyncReport, standardHQReport */
/*
    Ugly half-measure, because reports and UCR traditionally depend on a global standardHQReport
    variable that's defined in several different places. The UCR version of standardHQReport now
    lives in userreports/js/configurable_report.js, while the non-UCR version lives in this file
    and several custom reports still define standardHQReport as a global var.

    This file also controls some basic event handling for report pages, such as the "Apply" button.
*/
hqDefine("reports/js/standard_hq_report", [
    'jquery',
    'underscore',
    'hqwebapp/js/built',
    'bootstrap',
], function(
    $,
    _,
    hq
) {
    var standardReport = undefined,
        asyncReport = undefined;

    var getStandard = function() {
        if (typeof standardReport !== 'undefined') {
            return standardReport;
        }

        if (typeof standardHQReport !== 'undefined') {
            // Custom reports, notably ewsghana and ilsgateway
            standardReport = standardHQReport;
        } else {
            var ucr = "userreports/js/configurable_report";
            if (typeof COMMCAREHQ_MODULES[ucr] !== 'undefined') {
                // UCRs
                standardReport = hqImport(ucr).getStandardHQReport();
            } else if (typeof HQReport !== 'undefined') {
                // Standard reports
                var reportOptions = _.extend({}, hq.initialPageData.get('js_options'), {
                    emailSuccessMessage: gettext('Report successfully emailed'),
                    emailErrorMessage: gettext('An error occurred emailing you report. Please try again.'),
                });
                if (hq.initialPageData.get('startdate')) {
                    reportOptions.datespan = {
                        startdate: hq.initialPageData.get('startdate'),
                        enddate: hq.initialPageData.get('enddate'),
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
        if (typeof asyncReport !== 'undefined') {
            return asyncReport;
        }

        var reportOptions = hq.initialPageData.get('js_options') || {};
        if (reportOptions.slug && reportOptions.async) {
            var asyncHQReport = new HQAsyncReport({
                standardReport: getStandard(),
            });
            asyncHQReport.init();
            asyncReport = asyncHQReport;
        }

        return asyncReport;
    };

    $(function() {
        // Initialize reports. This must be done inside of a document ready handler
        // so that if this is UCR, userreports/js/configurable_report.js will
        // have been loaded and getStandard will execute the proper branch
        standardReport = getStandard(),
        asyncReport = getAsync();

        $('#apply-btn').on('click', function() {
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
