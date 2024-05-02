hqDefine("userreports/js/configurable_report", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");

    if (typeof define === 'function' && define.amd || window.USE_REQUIREJS) {
        throw new Error("This part of UCR is not yet migrated to RequireJS. Update the UCR logic in reports/js/standard_hq_report before removing this error.");
    }

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
                var label = hqImport('hqwebapp/js/bootstrap3/main').capitalize(builderType) + '-' + hqImport('hqwebapp/js/bootstrap3/main').capitalize(reportType);
                hqImport('userreports/js/report_analytix').track.event("View Report Builder Report", label);
            });
            hqImport('userreports/js/report_analytix').track.event("Loaded Report Builder Report");
            $editReportButton.click(function () {
                hqImport('analytix/js/kissmetrix').track.event("RBv2 - Click Edit Report");
            });
        }

        _.each(initialPageData.get("report_builder_events"), function (e) {
            hqImport('userreports/js/report_analytix').track.event.apply(this, e);
        });

        var urlSerialize = hqImport('reports/js/reports.util').urlSerialize;
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
        var standardHQReport = hqImport("reports/js/bootstrap3/hq_report").hqReport(reportOptions);
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

        var reportConfigModels = hqImport("reports/js/report_config_models"),
            reportConfigsView = reportConfigModels.reportConfigsViewModel({
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
            hqImport('userreports/js/report_analytix').track.event(
                initialPageData.get("builder_report_type"),
                'Load a report that was built in report builder'
            );
        }
    });

    return {
        getStandardHQReport: getStandardHQReport,
    };
});
