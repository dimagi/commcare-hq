hqDefine("userreports/js/configurable_report.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;

    $(function(){
        var $editReportButton = $("#edit-report-link");

        if (initial_page_data("created_by_builder")) {
            var $applyFiltersButton = $("#apply-filters");
            $applyFiltersButton.click(function(){
                window.analytics.usage("Report Viewer", "Apply Filters", '{{ report.spec.report_meta.builder_report_type }}');
            });
            gaTrackLink($editReportButton, 'Report Builder', 'Edit Report', '{{ report.spec.report_meta.builder_report_type }}');
            window.analytics.trackWorkflowLink($editReportButton, "Clicked Edit to enter the Report Builder");
            window.analytics.usage("Report Viewer", "View Report", '{{ report.spec.report_meta.builder_report_type }}');
        } else {
            gaTrackLink($editReportButton, 'Edit UCR', 'Edit UCR');
        }

        _.each(initial_page_data("report_builder_events"), function(e) {
            window.analytics.usage.apply(this, e);
        });

        // Poll the status of the data source
        if (!initial_page_data("is_static")) {
            var retrying = false;
            (function poll() {
                $.ajax({
                    url: hqImport("hqwebapp/js/urllib.js").reverse('configurable_data_source_status'),
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
                    }
                });
            })();
        }

        if (initial_page_data("created_by_builder")) {
            window.analytics.usage(
                    'Report Builder',
                    initial_page_data("builder_report_type"),
                    'Load a report that was built in report builder'
            )
        }
    });
});
