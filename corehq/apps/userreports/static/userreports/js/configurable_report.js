hqDefine("userreports/js/configurable_report", function () {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

    if (typeof define === 'function' && define.amd || window.USE_REQUIREJS) {
        throw new Error("This part of UCR is not yet migrated to RequireJS. Update the UCR logic in reports/js/standard_hq_report before removing this error.");
    }

    var getStandardHQReport = function (isFirstLoad) {
        if (!initial_page_data("standardHQReport")) {
            return undefined;
        }

        var $editReportButton = $("#edit-report-link");

        if (initial_page_data("created_by_builder") && !isFirstLoad) {
            var $applyFiltersButton = $("#apply-filters"),
                builder_type = initial_page_data("builder_report_type"),
                report_type = initial_page_data("type");
            $applyFiltersButton.click(function () {
                var label = hqImport('hqwebapp/js/bootstrap3/main').capitalize(builder_type) + '-' + hqImport('hqwebapp/js/bootstrap3/main').capitalize(report_type);
                hqImport('userreports/js/report_analytix').track.event("View Report Builder Report", label);
            });
            hqImport('userreports/js/report_analytix').track.event("Loaded Report Builder Report");
            $editReportButton.click(function () {
                hqImport('analytix/js/kissmetrix').track.event("RBv2 - Click Edit Report");
            });
        }

        _.each(initial_page_data("report_builder_events"), function (e) {
            hqImport('userreports/js/report_analytix').track.event.apply(this, e);
        });

        var urlSerialize = hqImport('reports/js/reports.util').urlSerialize;
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
            getReportRenderUrl: function (renderType) {
                var params = urlSerialize($('#paramSelectorForm'), ['format']);
                return window.location.pathname + "?format=" + renderType + "&" + params;
            },
        };
        if (initial_page_data('startdate')) {
            reportOptions.datespan = {
                startdate: initial_page_data('startdate'),
                enddate: initial_page_data('enddate'),
            };
        }
        var standardHQReport = hqImport("reports/js/hq_report").hqReport(reportOptions);
        standardHQReport.init();
        return standardHQReport;
    };

    $(function () {
        getStandardHQReport(true);

        // Bind the ReportConfigsViewModel to the save button.
        var defaultConfig = initial_page_data("default_config");
        if (initial_page_data("has_datespan")) {
            if (!defaultConfig.date_range) {
                defaultConfig.date_range = 'last7';
            }
            defaultConfig.has_ucr_datespan = true;
            defaultConfig.datespan_filters = initial_page_data("datespan_filters");
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
                items: initial_page_data("report_configs"),
                defaultItem: defaultConfig,
                saveUrl: hqImport("hqwebapp/js/initial_page_data").reverse("add_report_config"),
            });
        $("#savedReports").koApplyBindings(reportConfigsView);
        reportConfigsView.setUserConfigurableConfigBeingViewed(reportConfigModels.reportConfig(defaultConfig));

        $('#email-enabled').tooltip({
            placement: 'right',
            html: true,
            title: gettext("You can email a saved version<br />of this report."),
        });

        if (initial_page_data("created_by_builder")) {
            hqImport('userreports/js/report_analytix').track.event(
                initial_page_data("builder_report_type"),
                'Load a report that was built in report builder'
            );
        }
    });

    return {
        getStandardHQReport: getStandardHQReport,
    };
});
