hqDefine("userreports/js/configurable_report", [
    'jquery',
    'underscore',
    'analytix/js/kissmetrix',
    'hqwebapp/js/bootstrap3/main',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap3/hq_report',
    'reports/js/bootstrap3/report_config_models',
    'reports/js/util',
    'userreports/js/report_analytix',
    'userreports/js/base',
    'commcarehq',
], function (
    $,
    _,
    kissmetrics,
    hqMain,
    initialPageData,
    hqReport,
    reportConfigModels,
    util,
    analytics,
) {
    var getStandardHQReport = function (isFirstLoad) {
        if (!initialPageData.get("standardHQReport")) {
            return undefined;
        }

        var $editReportButton = $("#edit-report-link");

        if (initialPageData.get("created_by_builder") && !isFirstLoad) {
            var $applyFiltersButton = $("#apply-filters"),
                builderType = initialPageData.get("builder_report_type"),
                reportType = initialPageData.get("type");
            $applyFiltersButton.click(function () {
                var label = hqMain.capitalize(builderType) + '-' + hqMain.capitalize(reportType);
                analytics.track.event("View Report Builder Report", label);
            });
            analytics.track.event("Loaded Report Builder Report");
            $editReportButton.click(function () {
                kissmetrics.track.event("RBv2 - Click Edit Report");
            });
        }

        _.each(initialPageData.get("report_builder_events"), function (e) {
            analytics.track.event.apply(this, e);
        });

        var urlSerialize = util.urlSerialize;
        var reportOptions = {
            domain: initialPageData.get('domain'),
            urlRoot: initialPageData.get('url_root'),
            slug: initialPageData.get('slug'),
            subReportSlug: initialPageData.get('sub_slug'),
            type: initialPageData.get('type'),
            filterSet: initialPageData.get('filter_set'),
            needsFilters: initialPageData.get('needs_filters'),
            isExportable: initialPageData.get('is_exportable'),
            isExportAll: initialPageData.get('is_export_all'),
            isEmailable: initialPageData.get('is_emailable'),
            emailDefaultSubject: initialPageData.get('title'),
            emailSuccessMessage: gettext('Report successfully emailed'),
            emailErrorMessage: gettext('An error occurred emailing you report. Please try again.'),
            getReportRenderUrl: function (renderType) {
                var params = urlSerialize($('#paramSelectorForm'), ['format']);
                return window.location.pathname + "?format=" + renderType + "&" + params;
            },
        };
        if (initialPageData.get('startdate')) {
            reportOptions.datespan = {
                startdate: initialPageData.get('startdate'),
                enddate: initialPageData.get('enddate'),
            };
        }
        var standardHQReport = hqReport.hqReport(reportOptions);
        standardHQReport.init();
        return standardHQReport;
    };

    $(function () {
        getStandardHQReport(true);

        // Bind the ReportConfigsViewModel to the save button.
        var defaultConfig = initialPageData.get("default_config");
        if (initialPageData.get("has_datespan")) {
            if (!defaultConfig.date_range) {
                defaultConfig.date_range = 'last7';
            }
            defaultConfig.has_ucr_datespan = true;
            defaultConfig.datespan_filters = initialPageData.get("datespan_filters");
        } else {
            defaultConfig.date_range = null;
            defaultConfig.has_ucr_datespan = false;
            defaultConfig.datespan_filters = [];
        }
        if (!defaultConfig.datespan_slug) {
            defaultConfig.datespan_slug = null;
        }

        var reportConfigsView = reportConfigModels.reportConfigsViewModel({
            filterForm: $("#paramSelectorForm"),
            items: initialPageData.get("report_configs"),
            defaultItem: defaultConfig,
            saveUrl: initialPageData.reverse("add_report_config"),
        });
        $("#savedReports").koApplyBindings(reportConfigsView);
        reportConfigsView.setUserConfigurableConfigBeingViewed(reportConfigModels.reportConfig(defaultConfig));

        $('#email-enabled').tooltip({
            placement: 'right',
            html: true,
            title: gettext("You can email a saved version<br />of this report."),
        });

        if (initialPageData.get("created_by_builder")) {
            analytics.track.event(
                initialPageData.get("builder_report_type"),
                'Load a report that was built in report builder',
            );
        }
    });

    return {
        getStandardHQReport: getStandardHQReport,
    };
});
