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
    var formDefaults = {
        model_type: '',
        app_type: 'all',
        application: null,
        module: null,
        form: null,
        case_type: null,
    };

    // Interaction for the entire modal
    var createExportModel = function (options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, [], ['model_type']);

        var self = {};

        self.isLoaded = ko.observable(false);
        self.isSubmittingForm = ko.observable(false);
        self.showNoAppsError = ko.observable(false);
        self.hasNoCaseTypes = ko.observable(false);
        self.hasSpecialAppTypes = ko.observable(false);
        self.formLoadError = ko.observable('');
        self.formSubmissionError = ko.observable('');   // TODO: test

        // Form Data
        self.modelType = ko.observable(options.model_type);
        self.staticModelType = !!options.model_type;
        self.appType = ko.observable();
        self.application = ko.observable();
        self.caseType = ko.observable();
        self.module = ko.observable();
        self.form = ko.observable();
        self.selectedAppData = ko.observable({});
        self.selectedFormData = ko.observable({});
        self.selectedFormName = ko.observable('');

        self.isCaseModel = ko.computed(function () {
            return self.modelType() === 'case';
        });
        self.isFormModel = ko.computed(function () {
            return self.modelType() === 'form';
        });
        self.showAppType = ko.computed(function () {
            return self.hasSpecialAppTypes() || self.isFormModel();
        });

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
            return self.modelType()
                && self.appType()
                && self.application()
                && (self.module() || self.isCaseModel())
                && (self.form() || self.isCaseModel())
                && (self.caseType() || self.isFormModel());
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

        // Helper functions for initializing form
        self._select2Test = {};
        self._formSelect2Setter = function (observable, fieldSlug) {
            return function (field_data) {
                if (fieldSlug) {
                    observable('');
                    $('#div_id_' + fieldSlug).find("label").text(self._labels[fieldSlug]); 
                    var $formElem = $('#id_' + fieldSlug);
                    if ($formElem.length > 0) {
                        $formElem.select2({
                            data: field_data || [],
                            triggerChange: true,
                        }).select2('val', formDefaults[fieldSlug]).trigger('change');
                        $('#s2id_id_' + fieldSlug)
                            .find('.select2-choice').addClass('select2-default')
                            .find('.select2-chosen').text(self._placeholders[fieldSlug]);
                    }
                    self._select2Test[fieldSlug] = {    // TODO: what is this? code for running tests?
                        data: field_data,
                        placeholder: self._placeholders[fieldSlug],
                        defaults: formDefaults[fieldSlug],
                    };
                }
            };
        };
        self.setAppTypes = function () {
            self.appType(formDefaults.app_type);

            var $formElem = $('#id_app_type');
            if ($formElem.length > 0) {
                $formElem.select2({
                    data: self._app_types || [],
                    triggerChange: true,
                }).select2('val', formDefaults.app_type).trigger('change');
            }
            self._select2Test.app_type = {
                data: self._app_types || [],
                placeholder: null,
                defaults: formDefaults.app_type,
            };
        },
        self.setApps = self._formSelect2Setter(self.application, 'application');
        self.setModules = self._formSelect2Setter(self.module, 'module');
        self.setForms = self._formSelect2Setter(self.form, 'form');
        self.setCaseTypes = self._formSelect2Setter(self.caseType, 'case_type');
        self.resetForm = function () {
            if (!self.isLoaded()) {
                return;
            }

            self.setAppTypes();
            self.setApps(self._apps_by_type.all || []);
            self.setModules();
            self.setForms();
            self.setCaseTypes();
            self.selectedAppData({});
            self.selectedFormData({});
            self.hasNoCaseTypes(false);
        };

        // Helper functions for handling drilldown
        self.updateAppChoices = function () {
            var app_choices = self._apps_by_type[self.appType()];
            self.setApps(app_choices);
            self.selectedAppData({});
            self.selectedFormData({});
            self.hasNoCaseTypes(false);
            self.setModules();
            self.setForms();
            self.setCaseTypes();
        };
        self.modelType.subscribe(self.resetForm);
        self.application.subscribe(function (newValue) {
            if (newValue) {
                if (self.modelType() === 'form') {
                    var module_choices = self._modules_by_app[newValue];
                    self.setModules(module_choices);
                    self.selectedFormData({});
                    self.setForms();
                } else {
                    var case_type_choices = self._case_types_by_app[newValue];
                    self.setCaseTypes(case_type_choices);
                    self.hasNoCaseTypes(_.isEmpty(case_type_choices));
                }
            } else {
                self.caseType('');
                self.module('');
            }

            var currentApp = _.find(self._apps_by_type[self.appType()], function (app) {
                return app.id === newValue;
            });
            if (!currentApp) {
                self.selectedAppData({});
            } else {
                self.selectedAppData(_.extend(currentApp.data, {
                    name: currentApp.text,
                }));
            }
        });
        self.module.subscribe(function (newValue) {
            if (newValue) {
                var form_choices = self._forms_by_app_by_module[self.application()][newValue];
                self.setForms(form_choices);
            } else {
                self.form('');
            }
        });
        self.form.subscribe(function (newValue) {
            if (self.application() && self.module()) {
                var currentForm = _.find(self._forms_by_app_by_module[self.application()][self.module()], function (form) {
                    return form.id === newValue;
                });
                if (!currentForm) {
                    self.selectedFormData({});
                } else {
                    self.selectedFormData(_.extend(currentForm.data, {
                        name: currentForm.text,
                    }));
                }
            }
        });

        // Fetch form values on page load
        $.ajax({
            method: 'GET',
            url: initialPageData.reverse('get_app_data_drilldown_values'),
            data: {
                is_deid: initialPageData.get('is_deid'),    // TODO: introduce strictness to ipd?
                model_type: initialPageData.get('model_type'),
            },
            success: function (data) {
                self.showNoAppsError(data.app_types.length === 1 && data.apps_by_type.all.length === 0);
                if (!self.showNoAppsError()) {
                    self.hasSpecialAppTypes(data.app_types.length > 1);

                    self._labels = data.labels || {};
                    self._placeholders = data.placeholders || {};
                    self._app_types = data.app_types || [];
                    self._apps_by_type = data.apps_by_type || {};
                    self._modules_by_app = data.modules_by_app || {};
                    self._forms_by_app_by_module = data.forms_by_app_by_module || {};
                    self._case_types_by_app = data.case_types_by_app || {};

                    self.setAppTypes();
                    self.setApps(data.apps_by_type[self.appType()]);
                    self.setModules();
                    self.setForms();
                    self.setCaseTypes();
                }
                self.isLoaded(true);
            },
            error: function () {
                // TODO: test
                self.formLoadError('default');      // TODO: put the generic error directly in here
                self.isLoaded(true);
            },
        });

        return self;
    };

    $(function () {
        $("#create-export").koApplyBindings(createExportModel({
            model_type: initialPageData.get("model_type"),
        }));
        $('#createExportOptionsModal').on('show.bs.modal', function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked New Export");
        });
    });
});
