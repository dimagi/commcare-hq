/*
    This file also controls basic logic and event handling for report pages, such as the "Apply" button.
*/
hqDefine("reports/js/bootstrap5/standard_hq_report", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap5/hq_report',
], function (
    $,
    _,
    initialPageData,
    hqReportModule
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
        }
        return standardReport;
    };

    var getAsync = function () {
        if (typeof asyncReport !== 'undefined') {
            return asyncReport;
        }

        var reportOptions = initialPageData.get('js_options') || {};
        if (reportOptions.slug && reportOptions.async) {
            let promise = $.Deferred();
            require(["reports/js/bootstrap5/async"], function (asyncHQReportModule) {
                var asyncHQReport = asyncHQReportModule({
                    standardReport: getStandard(),
                });
                asyncHQReport.init();
                asyncReport = asyncHQReport;
                promise.resolve(asyncReport);
            });
            return promise;
        }

        return asyncReport;
    };

    // Initialize reports
    standardReport = getStandard();
    asyncReport = getAsync();

    $(function () {
        $('#apply-btn').on('click', function () {
            $('.hq-generic-report').trigger('apply-click');
        });

        $('[data-toggle="offcanvas"]').click(function () {
            $('.row-offcanvas').toggleClass('active');
        });

        $('.report-description-popover').popover({  /* todo B5: plugin:popover */
            placement: 'right',
            trigger: 'hover',
        });
    });

    return {
        getAsyncHQReport: getAsync,
        getStandardHQReport: getStandard,
    };
});
