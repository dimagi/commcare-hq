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
        self.hasNoCaseTypes = ko.observable(false);
        self.hasSpecialAppTypes = ko.observable(false); // TODO: test
        self.formLoadError = ko.observable('');
        self.formSubmissionError = ko.observable('');   // TODO: test

        // Form Data
        self.modelType = ko.observable();
        self.appType = ko.observable();
        self.application = ko.observable();
        self.form = ko.observable();
        self.selectedAppData = ko.observable({});
        self.selectedFormData = ko.observable({});
        self.selectedFormName = ko.observable('');

        self.showMislabeled = ko.observable(false);
        self.showSuggestions = ko.observable(false);
        self.showAppDoesNotExist = ko.observable(false);
        self.showDuplicate = ko.observable(false);
        self.duplicatePossibilities = ko.observableArray();
        self.restoreAppText = ko.observable('');
        self.restoreAppLink = ko.observable('');

        self.defaultFormLoadError = ko.computed(function () {
            return self.formLoadError() === 'default';
        });
        self.defaultFormSubmissionError = ko.computed(function () {
            return self.formSubmissionError() === 'default';
        });

        self.showHasNoCaseTypes = ko.computed(function () {
            return self.hasNoCaseTypes() && self.application();
        });

        self.showSubmissionCount = ko.computed(function () {
            return self.modelType() === 'form' && !_.isEmpty(self.selectedFormData());
        });
        self.submissionCountText = ko.observable('');

        // TODO: test
        self.selectedAppData.subscribe(function (newValue) {
            if (self.appType() === 'deleted' && self.application()) {
                self.restoreAppText(_.template(gettext("<%= name %> has been deleted."))({ name: newValue.name }));
                self.restoreAppLink(newValue.restoreUrl);
            } else {
                self.restoreAppText('');
                self.restoreAppLink('');
            }
        });

        self.selectedFormData.subscribe(function (newValue) {
            // Update form submission count message
            var text = '';
            if (self.modelType() === 'form') {
                if (newValue.submissions === 1) {
                    text = gettext('<%= count %> form submission available.');
                } else {
                    text = gettext('<%= count %> form submissions available.');
                }
                text = _.template(text)({ count: newValue.submissions, });
            }
            self.submissionCountText(text);

            // Display "Mislabeled" message
            self.showMislabeled(self.appType() === '_unknown' && !self.form() && !newValue.app_copy);

            // Display suggestions
            self.showSuggestions(self.appType() === '_unknown' && !self.form() && !newValue.no_suggestions);

            self.showAppDoesNotExist(newValue.app_does_not_exist);

            self.showDuplicate(newValue.duplicate);
            self.duplicatePossibilities(newValue.possibilities);
            self.selectedFormName(newValue.is_user_registration ? gettext('User Registration') : newValue.name);
        });

        self.showDrilldown = ko.computed(function () {
            return !self.showNoAppsError() && !self.formLoadError() && self.isLoaded() && !self.isSubmittingForm();
        });

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
