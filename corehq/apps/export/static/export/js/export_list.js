hqDefine("export/js/export_list.js", function() {
    'use strict';
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
        listExportsApp = window.angular.module('listExportsApp', ['hq.list_exports', 'hq.app_data_drilldown']);
    listExportsApp.config(["$httpProvider", function($httpProvider) {
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    listExportsApp.config(["djangoRMIProvider", function(djangoRMIProvider) {
        djangoRMIProvider.configure(initial_page_data("djng_current_rmi"));
    }]);
    listExportsApp.constant('formModalSelector', '#createExportOptionsModal');
    listExportsApp.constant('processApplicationDataFormSuccessCallback', function (data) {
        window.location = data.url;
    });
    listExportsApp.constant('bulk_download_url', initial_page_data("bulk_download_url"));
    listExportsApp.constant('legacy_bulk_download_url', initial_page_data("legacy_bulk_download_url"));
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
});
