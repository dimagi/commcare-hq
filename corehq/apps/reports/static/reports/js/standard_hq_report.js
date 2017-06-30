/* globals COMMCAREHQ_MODULES, HQReport, standardHQReport */
/*
    Ugly half-measure, because reports and UCR traditionally depend on a global standardHQReport
    variable that's defined in several different places. The UCR version of standardHQReport now
    lives in userreports/js/configurable_report.js, while the non-UCR version lives in this file
    and several custom reports still define standardHQReport as a global var.

    This file also controls some basic event handling for report pages, such as the "Apply" button.
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
            // Custom reports, notably ewsghana and ilsgateway
            standardReport = standardHQReport;
        } else {
            var ucr = "userreports/js/configurable_report.js";
            if (typeof COMMCAREHQ_MODULES[ucr] !== 'undefined') {
                // UCRs
                standardReport = hqImport(ucr).getStandardHQReport();
            } else if (typeof HQReport !== 'undefined') {
                // Standard reports
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
        $('#apply-btn').on('click', function() {
            $('.hq-generic-report').trigger('apply-click');
        });

        $('[data-toggle="offcanvas"]').click(function () {
            $('.row-offcanvas').toggleClass('active')
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
