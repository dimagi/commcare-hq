hqDefine("reports/js/bootstrap3/base", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'reports/js/filters/bootstrap3/main',
    'reports/js/bootstrap3/report_config_models',
    'reports/js/bootstrap3/tabular',
    'commcarehq',
], function (
    $,
    initialPageData,
    filtersMain,
    reportConfigModels,
) {
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

        $('#email-enabled').tooltip({
            placement: 'right',
            html: true,
            title: gettext("You can email a saved version<br />of this report."),
        });
    });
});
