hqDefine("export/js/export_list_main", function () {
    'use strict';

    /* Angular; to be deprecated */
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
        listExportsApp = window.angular.module('listExportsApp', ['hq.list_exports']);
    listExportsApp.config(["$httpProvider", function ($httpProvider) {
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    listExportsApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
        djangoRMIProvider.configure(initial_page_data("djng_current_rmi"));
    }]);
    listExportsApp.constant('bulk_download_url', initial_page_data("bulk_download_url"));
    listExportsApp.constant('modelType', initial_page_data("model_type"));
    listExportsApp.constant('staticModelType', initial_page_data("static_model_type"));
    listExportsApp.constant('filterFormElements', {
        emwf_form_filter: function () {
            return $('#id_emwf_form_filter');
        },
        emwf_case_filter: function () {
            return $('#id_emwf_case_filter');
        },
    });
    listExportsApp.constant('filterFormModalElement', function () {
        return $('#setFeedFiltersModal');
    });

    /* Knockout */
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
    });
});
