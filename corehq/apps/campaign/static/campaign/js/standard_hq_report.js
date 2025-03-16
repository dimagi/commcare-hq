/*
    This file also controls basic logic and event handling for report pages.
*/
hqDefine("campaign/js/standard_hq_report", [
    'jquery',
    'underscore',
    'bootstrap5',
    'hqwebapp/js/initial_page_data',
    'reports/js/util',
    'campaign/js/hq_report',
    'campaign/js/async_configurable_report',
], function (
    $,
    _,
    bootstrap,
    initialPageData,
    util,
    hqReportModule,
    asyncConfigurableReportModule,
) {
    let getStandard = function (reportOptions) {

        reportOptions.getReportRenderUrl = function (renderType) {
            const params = util.urlSerialize(reportOptions.filterForm, ['format']);
            return reportOptions.urlRoot + "?format=" + renderType + "&" + params;
        };

        let standardHQReport = hqReportModule.hqReport(reportOptions);
        standardHQReport.init();

        return standardHQReport;
    };

    var getAsync = function (reportOptions) {
        // let promise = $.Deferred();
        
        // require(["campaign/js/async_configurable_report"], function (asyncConfigurableReportModule) {
            var asyncReportOptions = _.extend(
                {},
                reportOptions,
                {
                    standardReport: getStandard(reportOptions),
                    reportId: reportOptions.subReportSlug || reportOptions.reportConfigurationId
                }
            );
            var asyncHQReport = asyncConfigurableReportModule(asyncReportOptions);
            asyncHQReport.init();
            // promise.resolve(asyncHQReport);
        // });
        // return promise;

        return asyncHQReport;
    };

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
        getAsyncHQReport: getAsync,
    };
});
