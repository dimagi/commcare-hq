hqDefine("export/js/export_list_main", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");

        $("#create-export").koApplyBindings(hqImport("export/js/create_export").createExportModel({
            model_type: initialPageData.get("model_type", true),
            drilldown_fetch_url: initialPageData.reverse('get_app_data_drilldown_values'),
            drilldown_submit_url: initialPageData.reverse('submit_app_data_drilldown_form'),
            page: {
                is_daily_saved_export: initialPageData.get('is_daily_saved_export', true),
                is_feed: initialPageData.get('is_feed', true),
                is_deid: initialPageData.get('is_deid', true),
                model_type: initialPageData.get('model_type', true),
            },
        }));
        $('#createExportOptionsModal').on('show.bs.modal', function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked New Export");
        });

        var modelType = initialPageData.get("model_type");
        $("#export-list").koApplyBindings(hqImport("export/js/export_list").exportListModel({
            exports: initialPageData.get("exports"),
            modelType: modelType,
            isDeid: initialPageData.get('is_deid'),
            urls: {
                commitFilters: initialPageData.reverse("commit_filters"),
                poll: initialPageData.reverse("get_saved_export_progress"),
                toggleEnabled: initialPageData.reverse("toggle_saved_export_enabled"),
                update: initialPageData.reverse("update_emailed_export_data"),
            },
        }));

        if (modelType === 'form') {
            hqImport('analytix/js/kissmetrix').track.event('Visited Export Forms Page');
        } else if (modelType === 'case') {
            hqImport('analytix/js/kissmetrix').track.event('Visited Export Cases Page');
        }
    });
});
