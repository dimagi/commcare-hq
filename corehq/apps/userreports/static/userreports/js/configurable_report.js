/* globals HQReport */
hqDefine("userreports/js/configurable_report", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

    var getStandardHQReport = function(isFirstLoad) {
        if (!initial_page_data("standardHQReport")) {
            return undefined;
        }

        var $editReportButton = $("#edit-report-link");

        if (initial_page_data("created_by_builder") && !isFirstLoad) {
            var $applyFiltersButton = $("#apply-filters"),
                builder_type = initial_page_data("builder_report_type"),
                report_type = initial_page_data("type");
            $applyFiltersButton.click(function () {
                var label = hqImport('hqwebapp/js/main').capitalize(builder_type) + '-' + hqImport('hqwebapp/js/main').capitalize(report_type);
                hqImport('userreports/js/report_analytics').track.event("View Report Builder Report", label);
            });
            hqImport('userreports/js/report_analytics').track.event("Loaded Report Builder Report");
            $editReportButton.click(function () {
                hqImport('analytix/js/kissmetrics').track.event("RBv2 - Click Edit Report");
            });
        }

        _.each(initial_page_data("report_builder_events"), function(e) {
            hqImport('userreports/js/report_analytics').track.event.apply(this, e);
        });

        // Poll the status of the data source
        if (!initial_page_data("is_static")) {
            var retrying = false;
            (function poll() {
                $.ajax({
                    url: hqImport("hqwebapp/js/initial_page_data").reverse('configurable_data_source_status'),
                    dataType: 'json',
                    success: function(data) {
                        if (data.isBuilt){
                            $('#built-warning').addClass('hide');
                            if (retrying){
                                location.reload();
                            } else if ($('#report-filters').find('.control-label').length === 0) {
                                $('#report-filters').submit();
                            }
                        } else {
                            retrying = true;
                            $('#built-warning').removeClass('hide');
                            setTimeout(poll, 5000);
                        }
                    },
                });
            })();
        }

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
            getReportRenderUrl: function(renderType, additionalParams) {
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
        var standardHQReport = new HQReport(reportOptions);
        standardHQReport.init();
        return standardHQReport;
    };

    $(function() {
        getStandardHQReport(true);

        // Bind the ReportConfigsViewModel to the save button.
        var defaultConfig = initial_page_data("default_config");
        if (initial_page_data("has_datespan")) {
            if(!defaultConfig.date_range) {
                defaultConfig.date_range = 'last7';
            }
            defaultConfig.has_ucr_datespan = true;
            defaultConfig.datespan_filters = initial_page_data("datespan_filters");
        } else {
            defaultConfig.date_range = null;
            defaultConfig.has_ucr_datespan = false;
            defaultConfig.datespan_filters = [];
        }
        if(!defaultConfig.datespan_slug) {
            defaultConfig.datespan_slug = null;
        }
        $("#savedReports").reportUserConfigurableConfigEditor({
            filterForm: $("#paramSelectorForm"),
            items: initial_page_data("report_configs"),
            defaultItem: defaultConfig,
            saveUrl: hqImport("hqwebapp/js/initial_page_data").reverse("add_report_config"),
        });

        $('#email-enabled').tooltip({
            placement: 'right',
            html: true,
            title: gettext("You can email a saved version<br />of this report."),
        });

        if (initial_page_data("created_by_builder")) {
            hqImport('userreports/js/report_analytics').track.event(
                    initial_page_data("builder_report_type"),
                    'Load a report that was built in report builder'
            );
        }
    });

    return {
        getStandardHQReport: getStandardHQReport,
    };
});
