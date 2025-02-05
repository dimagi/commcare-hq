/*
    This file also controls basic logic and event handling for report pages.
*/
hqDefine("reports/js/bootstrap3/standard_hq_report", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    initialPageData,
) {
    var standardReport = undefined,
        asyncReport = undefined;

    var getStandard = function () {
        if (typeof standardReport !== 'undefined') {
            return standardReport;
        }
        import("userreports/js/configurable_report").then(function (ucrModule) {
            standardReport = ucrModule.getStandardHQReport();
        });

        return standardReport;
    };

    var getAsync = function () {
        if (typeof asyncReport !== 'undefined') {
            return asyncReport;
        }

        var reportOptions = initialPageData.get('js_options') || {};
        if (reportOptions.slug && reportOptions.async) {
            let promise = $.Deferred();
            require(["reports/js/bootstrap3/async"], function (asyncHQReportModule) {
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
