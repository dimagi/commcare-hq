import 'commcarehq';

import $ from 'jquery';

import initialPageData from 'hqwebapp/js/initial_page_data';
import filtersMain from 'reports/js/filters/bootstrap5/main';
import reportConfigModels from 'reports/js/bootstrap5/report_config_models';

import 'reports/js/bootstrap3/tabular';

$(function () {
    filtersMain.init();

    var defaultConfig = initialPageData.get('default_config') || {};
    if (initialPageData.get('has_datespan')) {
        defaultConfig.date_range = 'last7';
    } else {
        defaultConfig.date_range = null;
    }
    defaultConfig.has_ucr_datespan = false;
    defaultConfig.datespan_filters = [];
    defaultConfig.datespan_slug = null;

    var $savedReports = $("#savedReports");
    if ($savedReports.length) {
        var reportConfigsView = reportConfigModels.reportConfigsViewModel({
            filterForm: $("#reportFilters"),
            items: initialPageData.get('report_configs'),
            defaultItem: defaultConfig,
            saveUrl: initialPageData.reverse("add_report_config"),
        });
        $savedReports.koApplyBindings(reportConfigsView);
        reportConfigsView.setConfigBeingViewed(reportConfigModels.reportConfig(defaultConfig));
    }

    $('#email-enabled').tooltip({  /* todo B5: plugin:tooltip */
        placement: 'right',
        html: true,
        title: gettext("You can email a saved version<br />of this report."),
    });
});
