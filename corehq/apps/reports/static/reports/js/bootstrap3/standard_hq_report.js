/*
    This file also controls basic logic and event handling for report pages.
*/
hqDefine("reports/js/bootstrap3/standard_hq_report", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'reports/js/util',
    'reports/js/bootstrap3/hq_report',
], function (
    $,
    _,
    initialPageData,
    util,
    hqReportModule,
) {
    var standardReport = undefined,
        asyncReport = undefined;

    var getStandard = function () {
        if (typeof standardReport !== 'undefined') {
            return standardReport;
        }

        var reportOptions = _.extend({}, initialPageData.get('js_options'), {
            emailSuccessMessage: gettext('Report successfully emailed'),
            emailErrorMessage: gettext('An error occurred emailing your report. Please try again.'),
        });

        if (initialPageData.get('override_report_render_url')) {
            reportOptions.getReportBaseUrl = function (renderType) {
                return reportOptions.url + "?format=" + renderType;
            };
            reportOptions.getReportParams = function () {
                return util.urlSerialize($('#paramSelectorForm'), ['format']);
            };
            reportOptions.getReportRenderUrl = function (renderType) {
                var baseUrl = self.getReportBaseUrl(renderType);
                var paramString = self.getReportParams();
                return baseUrl + "&" + paramString;
            };
        }

        if (initialPageData.get('startdate')) {
            reportOptions.datespan = {
                startdate: initialPageData.get('startdate'),
                enddate: initialPageData.get('enddate'),
            };
        }

        var standardHQReport = hqReportModule.hqReport(reportOptions);
        standardHQReport.init();
        standardReport = standardHQReport;

        return standardReport;
    };

    var getAsync = function () {
        if (typeof asyncReport !== 'undefined') {
            return asyncReport;
        }

        var reportOptions = initialPageData.get('js_options') || {};
        if (reportOptions.slug && reportOptions.async) {
            let promise = $.Deferred();
            import("reports/js/bootstrap3/async").then(function (asyncHQReportModule) {
                var asyncHQReport = asyncHQReportModule.default({
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
        $('[data-toggle="offcanvas"]').click(function () {
            $('.row-offcanvas').toggleClass('active');
        });

        $('.report-description-popover').popover({
            placement: 'right',
            trigger: 'hover',
        });
    });

    return {
        getStandardHQReport: getStandard,
    };
});
