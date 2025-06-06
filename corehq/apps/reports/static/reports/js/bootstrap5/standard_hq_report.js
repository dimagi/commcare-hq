/*
    This file also controls basic logic and event handling for report pages.
*/
import $ from "jquery";
import _ from "underscore";
import { Popover } from "bootstrap5";
import initialPageData from "hqwebapp/js/initial_page_data";
import util from "reports/js/util";
import hqReportModule from "reports/js/bootstrap5/hq_report";

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
        reportOptions.getReportRenderUrl = function (renderType) {
            var params = util.urlSerialize($('#paramSelectorForm'), ['format']);
            return window.location.pathname + "?format=" + renderType + "&" + params;
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
        import("reports/js/bootstrap5/async").then(function (asyncHQReportModule) {
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

    $('[data-hq-toggle]').click(function () {
        $($(this).data('hqToggle')).toggleClass('active');
    });

    const reportsWithDescriptions = document.getElementsByClassName('report-description-popover');
    Array.from(reportsWithDescriptions).forEach((elem) => {
        new Popover(elem, {
            title: elem.dataset.title,
            content: elem.dataset.content,
            placement: 'right',
            trigger: 'hover',
        });
    });
});

export default {
    getStandardHQReport: getStandard,
};
