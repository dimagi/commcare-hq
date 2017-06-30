/* globals COMMCAREHQ_MODULES, standardHQReport */
/*
    Ugly half-measure, because reports and UCR traditionally depend on a global standardHQReport
    variable that's defined in several different places. The UCR version of standardHQReport now
    lives in userreports/js/configurable_report.js, whereas the other standardHQReport vars are
    still defined globally. This module's sole purpose is to fetch the correct standardHQReport,
    if it exists at all.
*/
hqDefine("reports/js/standard_hq_report.js", function() {
    var get = function() {
        if (typeof standardHQReport !== 'undefined') {
            return standardHQReport;
        }
        var ucr = "userreports/js/configurable_report.js";
        if (typeof COMMCAREHQ_MODULES[ucr] !== 'undefined') {
            return hqImport(ucr).getStandardHQReport();
        }
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
        var reportOptions = {
            domain: initial_page_data('domain'),
            urlRoot: initial_page_data('url_root'),
            slug: initial_page_data('slug'),
            subReportSlug: initial_page_data('sub_slug'),
            type: initial_page_data('type'),
            filterSet: initial_page_data('filter_set'),
            needsFilters: initial_page_data('needs_filters'),
            isExportable: initial_page_data('is_exportable'),
            isExportAll: initial_page_data('is_export_all'),
            isEmailable: initial_page_data('is_emailable'),
            emailDefaultSubject: initial_page_data('title'),
            emailSuccessMessage: gettext('Report successfully emailed'),
            emailErrorMessage: gettext('An error occurred emailing you report. Please try again.'),
        };
        if (initial_page_data('startdate')) {
            reportOptions.datespan = {
                startdate: initial_page_data('startdate'),
                enddate: initial_page_data('enddate'),
            };
        }
        var standardHQReport = new HQReport(reportOptions);
        standardHQReport.init();
        return standardHQReport;
    };

    return {
        getStandardHQReport: get,
    };
});
