/*
    This file also controls basic logic and event handling for report pages.
*/
hqDefine("reports/js/bootstrap5/standard_hq_report", [
    'jquery',
    'underscore',
    'bootstrap5',
    'hqwebapp/js/initial_page_data',
    'reports/js/util',
    'reports/js/bootstrap5/hq_report',
], function (
    $,
    _,
    bootstrap,
    initialPageData,
    util,
    hqReportModule,
) {
    var standardReport = undefined,
        asyncReport = undefined;

    var getStandard = function (options) {
        if (!options && typeof standardReport !== 'undefined') {
            return standardReport;
        }

        var reportOptions = _.extend({}, initialPageData.get('js_options'), {
            emailSuccessMessage: gettext('Report successfully emailed'),
            emailErrorMessage: gettext('An error occurred emailing your report. Please try again.'),
        }, options);

        if (initialPageData.get('override_report_render_url')) {
            reportOptions.getReportBaseUrl = function (renderType) {
                return reportOptions.url + "?format=" + renderType;
            };
            reportOptions.getReportParams = function () {
                return util.urlSerialize($('#paramSelectorForm' + reportOptions.html_id_suffix), ['format']);
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

        if (!options) {
            standardReport = standardHQReport;
            return standardReport;
        }
        return standardHQReport;
    };

    var getAsync = function (options) {
        if (!options && typeof asyncReport !== 'undefined') {
            return asyncReport;
        }

        var reportOptions = _.extend({}, initialPageData.get('js_options'), options);
        if (reportOptions.slug && reportOptions.async) {
            let promise = $.Deferred();
            import("reports/js/bootstrap5/async").then(function (asyncHQReportModule) {
                var asyncHQReport = asyncHQReportModule.default({
                    html_id_suffix: options.html_id_suffix,
                    standardReport: getStandard(options),
                });
                asyncHQReport.init();
                if (!options) {
                    asyncReport = asyncHQReport;
                    promise.resolve(asyncReport);
                } else {
                    promise.resolve(asyncHQReport);
                }
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
        getAsyncHQReport: getAsync,
    };
});
