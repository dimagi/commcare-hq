(function (angular, undefined) {
    'use strict';
    // module: hq.app_data_drilldown

    /* This is a module for drilling down to the form based on app type,
     * application, and module.
     * Use ApplicationDataRMIHelper to generate the correct response in
     * the djangoRMI method of your view.
     * */

    var app_drilldown = angular.module('hq.app_data_drilldown', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages'
    ]);

    // defaults
    app_drilldown.constant('formFieldSlugs', {
        app_type: 'app_type',
        application: 'application',
        module: 'module',
        form: 'form',
        case_type: 'case_type'
    });
    app_drilldown.constant('formDefaults', {
        app_type: 'all',
        application: null,
        module: null,
        form: null,
        case_type: null
    });
    app_drilldown.constant('djangoRMICallbackName', 'submit_app_data_drilldown_form');
    app_drilldown.constant('processApplicationDataFormSuccessCallback', function (data) {
        console.log('success');
        console.log(data);
    });
    app_drilldown.constant('formModalSelector', null);

    var selectControllers = {};
    selectControllers.DrilldownToFormController = function (
        $scope, djangoRMI, formFieldSlugs, formDefaults, djangoRMICallbackName,
        processApplicationDataFormSuccessCallback, formModalSelector
    ) {
        var self = this;
        $scope._ = _;  // use underscore.js in templates

        $scope.showNoAppsError = false;
        $scope.formLoadError = null;
        $scope.isLoaded = false;

        $scope.hasSpecialAppTypes = false;
        $scope.hasNoCaseTypes = false;

        $scope.isSubmittingForm = false;
        $scope.formSubmissionError = null;

        $scope.formData = formDefaults;

        self._placeholders = {};
        self._app_types = [];
        self._apps_by_type = {};
        self._modules_by_app = {};
        self._forms_by_app_by_module = {};
        self._case_types_by_app = {};

        self._select2Test = {};

        var _formElemGetter = function(fieldSlug) {
            return $('#id_' + fieldSlug);
        };

        var _formSelect2Setter = function (fieldSlug) {
            return function (field_data) {
                if (fieldSlug) {
                    $scope.formData[fieldSlug] = '';
                    var $formElem = _formElemGetter(fieldSlug);
                    if ($formElem.length > 0) {
                        $formElem.select2({
                            data: field_data || [],
                            triggerChange: true
                        }).select2('val', formDefaults[fieldSlug]).trigger('change');
                        $('#s2id_id_' + fieldSlug)
                            .find('.select2-choice').addClass('select2-default')
                            .find('.select2-chosen').text(self._placeholders[fieldSlug]);
                    }
                    self._select2Test[fieldSlug] = {
                        data: field_data,
                        placeholder: self._placeholders[fieldSlug],
                        defaults: formDefaults[fieldSlug]
                    };
                }
            };
        };

        var util = {
            setAppTypes: function () {
                $scope.formData.app_type = formDefaults.app_type;

                var $formElem = _formElemGetter('app_type');
                if ($formElem.length > 0) {
                    $formElem.select2({
                        data: self._app_types || [],
                        triggerChange: true
                    }).select2('val', formDefaults.app_type).trigger('change');
                }
                self._select2Test.app_type = {
                    data: self._app_types || [],
                    placeholder: null,
                    defaults: formDefaults.app_type
                };
            },
            setApps: _formSelect2Setter(formFieldSlugs.application),
            setModules: _formSelect2Setter(formFieldSlugs.module),
            setForms: _formSelect2Setter(formFieldSlugs.form),
            setCaseTypes: _formSelect2Setter(formFieldSlugs.case_type)
        };

        $scope.resetForm = function () {
            util.setAppTypes();
            util.setApps(self._apps_by_type.all || []);
            util.setModules();
            util.setForms();
            util.setCaseTypes();
            $scope.selectedAppData = {};
            $scope.selectedFormData = {};
        };

        if (formModalSelector) {
            $(formModalSelector).on('hidden.bs.modal', function () {
                $scope.resetForm();
            });
        }

        self._numRetries = 0;
        self._handleError = function () {
            if (self._numRetries > 3) {
                $scope.formLoadError = 'default';
                $scope.isLoaded = true;
                return;
            }
            self._numRetries ++;
            self._initializeForm();
        };

        self._initializeForm = function () {
            djangoRMI.get_app_data_drilldown_values({})
                .success(function (data) {
                    if (data.success) {
                        $scope.showNoAppsError = data.app_types.length === 1 && data.apps_by_type.all.length === 0;
                        if (!$scope.showNoAppsError) {
                            self._placeholders = data.placeholders || {};
                            self._app_types = data.app_types || [];
                            $scope.hasSpecialAppTypes = data.app_types.length > 1;
                            self._apps_by_type = data.apps_by_type || {};
                            self._modules_by_app = data.modules_by_app || {};
                            self._forms_by_app_by_module = data.forms_by_app_by_module || {};
                            self._case_types_by_app = data.case_types_by_app || {};
                            util.setAppTypes();
                            util.setApps(data.apps_by_type[$scope.formData.app_type]);
                            util.setModules();
                            util.setForms();
                            util.setCaseTypes();
                        }
                    } else {
                        $scope.formLoadError = data.error;
                    }
                    $scope.isLoaded = true;
                })
                .error(self._handleError);
        };
        self._initializeForm();

        $scope.updateAppChoices = function () {
            var app_choices = self._apps_by_type[$scope.formData.app_type];
            util.setApps(app_choices);
            $scope.selectedAppData = {};
            $scope.selectedFormData = {};
            $scope.hasNoCaseTypes = false;
            util.setModules();
            util.setForms();
            util.setCaseTypes();
        };

        $scope.updateModuleChoices = function () {
            var module_choices = self._modules_by_app[$scope.formData.application];
            util.setModules(module_choices);
            $scope.selectedFormData = {};
            util.setForms();
        };

        $scope.updateFormChoices = function () {
            if ($scope.formData.application && $scope.formData.module) {
                var form_choices = self._forms_by_app_by_module[$scope.formData.application][$scope.formData.module];
                util.setForms(form_choices);
            }
        };

        $scope.updateCaseTypeChoices = function () {
            var case_type_choices = self._case_types_by_app[$scope.formData.application];
            util.setCaseTypes(case_type_choices);
            $scope.hasNoCaseTypes = _.isEmpty(case_type_choices);
        };

        $scope.handleSubmitForm = function () {
            $scope.isSubmittingForm = true;

            // Immediately copy form data object so that if modal is
            // accidentally dismissed, data is still properly sent
            var formData = _.clone($scope.formData);

            djangoRMI[djangoRMICallbackName]({
                formData: formData
            })
            .success(function (data) {
                if (data.success) {
                    processApplicationDataFormSuccessCallback(data);
                } else {
                    $scope.isSubmittingForm = false;
                    $scope.formSubmissionError = data.error;
                }
            })
            .error(function () {
                $scope.isSubmittingForm = false;
                $scope.formSubmissionError = 'default';
            });
        };

        $scope.selectedAppData = {};
        $scope.$watch('formData.application', function (curAppId) {
            var currentApps = _.filter(self._apps_by_type[$scope.formData.app_type], function (app) {
                return app.id === curAppId;
            });
            if (currentApps.length === 0) {
                $scope.selectedAppData = {};
            } else {
                var app_data = currentApps[0].data;
                app_data.name = currentApps[0].text;
                $scope.selectedAppData = app_data;
            }
        });

        $scope.selectedFormData = {};
        $scope.$watch('formData.form', function (curFormId) {
            if ($scope.formData.application && $scope.formData.module) {
                var curForms = _.filter(self._forms_by_app_by_module[$scope.formData.application][$scope.formData.module], function (form) {
                    return form.id === curFormId;
                });
                if (curForms.length === 0) {
                    $scope.selectedFormData = {};
                } else {
                    var form_data = curForms[0].data;
                    form_data.name = curForms[0].text;
                    $scope.selectedFormData = form_data;
                }
            }
        });
    };
    app_drilldown.controller(selectControllers);

}(window.angular));
