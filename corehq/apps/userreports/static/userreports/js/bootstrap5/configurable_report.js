import "commcarehq";
import $ from "jquery";
import _ from "underscore";
import kissmetrics from "analytix/js/kissmetrix";
import hqMain from "hqwebapp/js/bootstrap5/main";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqReport from "reports/js/bootstrap5/hq_report";
import reportConfigModels from "reports/js/bootstrap5/report_config_models";
import standardHQReportModule from "reports/js/bootstrap5/standard_hq_report";
import analytics from "userreports/js/report_analytix";
import "userreports/js/bootstrap5/base";

$(function () {
    standardHQReportModule.getStandardHQReport();

    // Set up analytics
    if (initialPageData.get("created_by_builder")) {
        var $applyFiltersButton = $("#apply-filters"),
            builderType = initialPageData.get("builder_report_type"),
            reportType = initialPageData.get("type");
        $applyFiltersButton.click(function () {
            var label = hqMain.capitalize(builderType) + '-' + hqMain.capitalize(reportType);
            analytics.track.event("View Report Builder Report", label);
        });
        analytics.track.event("Loaded Report Builder Report");
        $("#edit-report-link").click(function () {
            kissmetrics.track.event("RBv2 - Click Edit Report");
        });
    }

    // More analytics
    _.each(initialPageData.get("report_builder_events"), function (e) {
        analytics.track.event.apply(this, e);
    });

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

    $('#email-enabled').tooltip({  /* todo B5: js-tooltip */
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
