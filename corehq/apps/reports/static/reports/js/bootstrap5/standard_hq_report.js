/*
    This file also controls basic logic and event handling for report pages.
*/
hqDefine("reports/js/bootstrap5/standard_hq_report", [
    'jquery',
    'underscore',
    'bootstrap5',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    bootstrap,
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

        $('[data-hq-toggle]').click(function () {
            $($(this).data('hqToggle')).toggleClass('active');
        });

        const reportsWithDescriptions = document.getElementsByClassName('report-description-popover');
        Array.from(reportsWithDescriptions).forEach((elem) => {
            new bootstrap.Popover(elem, {
                title: elem.dataset.title,
                content: elem.dataset.content,
                placement: 'right',
                trigger: 'hover',
            });
        });
    });

    return {
        getStandardHQReport: getStandard,
    };
});
