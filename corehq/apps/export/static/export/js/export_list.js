hqDefine("export/js/export_list", function () {
    'use strict';

    /* Angular; to be deprecated */
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
        listExportsApp = window.angular.module('listExportsApp', ['hq.list_exports', 'hq.app_data_drilldown']);
    listExportsApp.config(["$httpProvider", function ($httpProvider) {
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    listExportsApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
        djangoRMIProvider.configure(initial_page_data("djng_current_rmi"));
    }]);
    listExportsApp.constant('formModalSelector', '#createExportOptionsModal');
    listExportsApp.constant('processApplicationDataFormSuccessCallback', function (data) {
        window.location = data.url;
    });
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
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    var createExportModel = function () {
        var self = {};

        self.isLoaded = ko.observable(false);
        self.isSubmittingForm = ko.observable(false);
        self.showNoAppsError = ko.observable(false);
        self.formLoadError = ko.observable(false);

        self.isValid = ko.computed(function () {
            // TODO
            return true;
        });

        self.showSubmit = ko.computed(function () {
            return !self.showNoAppsError() && !self.formLoadError();
        });
        self.disableSubmit = ko.computed(function () {
            return !self.isValid() || self.isSubmittingForm();
        });

        self.handleSubmitForm = function () {
            // TODO
            return false;
        };

        return self;
    };

    $(function () {
        $("#create-export").koApplyBindings(createExportModel());
    });
});
