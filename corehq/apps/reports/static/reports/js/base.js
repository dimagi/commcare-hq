hqDefine("reports/js/base.js", function() {
    $(function() {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
        var defaultConfig = initial_page_data('default_config') || {};
        if (initial_page_data('has_datespan')) {
            defaultConfig.date_range = 'last7';
        } else {
            defaultConfig.date_range = null;
        }
        defaultConfig.has_ucr_datespan = false;
        defaultConfig.datespan_filters = [];
        defaultConfig.datespan_slug = null;

        var $savedReports = $("#savedReports");
        if ($savedReports.length) {
            $savedReports.reportConfigEditor({
                filterForm: $("#reportFilters"),
                items: initial_page_data('report_configs'),
                defaultItem: defaultConfig,
                saveUrl: hqImport("hqwebapp/js/urllib.js").reverse("add_report_config"),
            });
        }

        $('#email-enabled').tooltip({
            placement: 'right',
            html: true,
            title: gettext("You can email a saved version<br />of this report."),
        });
    });
});
