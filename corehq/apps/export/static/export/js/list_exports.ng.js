(function (angular, undefined) {
    'use strict';
    // module: hq.list_exports

    /* This module is for helping fetching and showing a list of exports,
     * and activating bulk export download, as well as single export download.
      * */

    var list_exports = angular.module('hq.list_exports', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages'
    ]);

    var exportsControllers = {};
    exportsControllers.ListExportsController = function (
        $scope, djangoRMI
    ) {
        var self = {};
        $scope._ = _;  // allow use of underscore.js within the template
        $scope.hasLoaded = false;
        $scope.exports = [];
        $scope.exportsListError = null;

        self._numTries = 0;
        self._getExportsList = function () {
            // The method below lives in the subclasses of
            // BaseExportListView.
            djangoRMI.get_exports_list({})
                .success(function (data) {
                    if (data.success) {
                        $scope.exports = data.exports;
                    } else {
                        $scope.exportsListError = data.error;
                    }
                    $scope.hasLoaded = true;
                })
                .error(function () {
                    // Retry in case the connection was flaky.
                    if (self._numTries > 3) {
                        $scope.hasLoaded = true;
                        $scope.exportsListError = 'default';
                    }
                    self._numTries ++;
                    self._getExportsList();
                });
        };
        self._getExportsList();

        // For Bulk Export
        $scope.showBulkExportDownload = false;
        $scope.bulkExportList = '';

        $scope.updateBulkStatus = function () {
            var selectedExports = _.filter($scope.exports, function (exp) {
                return !!exp.addedToBulk;
            });
            $scope.showBulkExportDownload = !_.isEmpty(selectedExports);
            $scope.bulkExportList = JSON.stringify(selectedExports);
            $('input[name="export_list"]').val(JSON.stringify(selectedExports));
        };
        $scope.selectAll = function () {
            _.each($scope.exports, function (exp) {
                exp.addedToBulk = true;
            });
            $scope.updateBulkStatus();
        };
        $scope.selectNone = function () {
            _.each($scope.exports, function (exp) {
                exp.addedToBulk = false;
            });
            $scope.updateBulkStatus();
        };
    };

    exportsControllers.CreateExportController = function (
        $scope, djangoRMI
    ) {
        var self = {};
        $scope._ = _;  // use underscore.js in templates
        $scope.showNoAppsError = false;
        $scope.formLoadError = null;
        $scope.isLoaded = false;
        $scope.hasNoCaseTypes = false;
        $scope.isFetchingUrl = false;

        var $formElem = {
            get_app: function () {
                return $('#id_application');
            },
            get_module: function () {
                return $('#id_module');
            },
            get_form: function () {
                return $('#id_form');
            },
            get_case_type: function () {
                return $('#id_case_type');
            }
        };
        $scope.createForm = {
            application: '',
            module: '',
            form: '',
            case_type: ''
        };
        self._placeholders = {};
        self._modules = {};
        self._forms = {};
        self._case_types = {};

        var $formSelect = {
            clearApp: function () {
                $formElem.get_app().select2('val', null).trigger('change');
                $scope.createForm.application = '';
                $('#s2id_id_application')
                    .find('.select2-choice').addClass('select2-default')
                    .find('.select2-chosen').text(self._placeholders.application);
            },
            setApps: function (app_data) {
                $formElem.get_app().select2({
                    data: app_data || [],
                    triggerChange: true
                });
            },
            setModules: function (module_data) {
                $scope.createForm.module = '';
                if ($formElem.get_module()) {
                   $formElem.get_module().select2({
                       data: module_data || [],
                       triggerChange: true
                   }).select2('val', null).trigger('change');
                   $('#s2id_id_module')
                       .find('.select2-choice').addClass('select2-default')
                       .find('.select2-chosen').text(self._placeholders.module);
                }

            },
            setForms: function (form_data) {
                $scope.createForm.form = '';
                if ($formElem.get_form()) {
                    $formElem.get_form().select2({
                        data: form_data || [],
                        triggerChange: true
                    }).select2('val', null).trigger('change');
                    $('#s2id_id_form')
                        .find('.select2-choice').addClass('select2-default')
                        .find('.select2-chosen').text(self._placeholders.form);
                }
            },
            setCaseTypes: function (case_type_data) {
                $scope.createForm.case_type = '';
                if ($formElem.get_case_type()) {
                   $formElem.get_case_type().select2({
                       data: case_type_data || [],
                       triggerChange: true
                   }).select2('val', null).trigger('change');
                   $('#s2id_id_case_type')
                       .find('.select2-choice').addClass('select2-default')
                       .find('.select2-chosen').text(self._placeholders.case_type);
                }

            }
        };

        $('#createExportOptionsModal').on('hide.bs.modal', function () {
            $formSelect.clearApp();
            $formSelect.setModules();
            $formSelect.setForms();
            $formSelect.setCaseTypes();
        });

        $scope.updateCaseTypes = function () {
            console.log(self._case_types);
            var case_types = self._case_types[$scope.createForm.application];
            $scope.hasNoCaseTypes = _.isEmpty(case_types);
            $formSelect.setCaseTypes(case_types);
        };

        $scope.updateModules = function () {
            $formSelect.setModules(self._modules[$scope.createForm.application]);
            $formSelect.setForms();
        };

        $scope.updateForms = function () {
            var formOptions = _.filter(
                self._forms[$scope.createForm.application],
                function (form) {
                    return form.module === $scope.createForm.module;
                }
            );
            $formSelect.setForms(formOptions);
        };

        $scope.handleCreateExport = function () {
            $scope.isFetchingUrl = true;

            // Immediately copy form data object so that if modal is
            // accidentally dismissed, data is still properly sent to server
            var formData = _.clone($scope.createForm);

            djangoRMI.process_create_form({
                createFormData: formData
            })
            .success(function (data) {
                if (data.success) {
                    window.location = data.url;
                } else {
                    $scope.isFetchingUrl = false;
                    $scope.fetchingUrlError = data.error;
                }
            })
            .error(function () {
                $scope.isFetchingUrl = false;
                $scope.fetchingUrlError = 'default';
            });
        };

        self._numRetries = 0;
        self._handleError = function () {
            if (self._numRetries > 3) {
                $scope.formLoadError = 'default';
                $scope.isLoaded = true;
            }
            self._numRetries ++;
            self._initializeForm();
        };

        self._initializeForm = function () {
            djangoRMI.get_initial_form_data({})
                .success(function (data) {
                    if (data.success) {
                        if (_.isEmpty(data.apps)) {
                            $scope.showNoAppsError = true;
                        } else {
                            self._modules = data.modules;
                            self._forms = data.forms;
                            self._case_types = data.case_types;
                            self._placeholders = data.placeholders;
                            $formSelect.setApps(data.apps);
                            $formSelect.setModules();
                            $formSelect.setForms();
                            $formSelect.setCaseTypes();
                        }
                    } else {
                        $scope.formLoadError = data.error;
                    }
                    $scope.isLoaded = true;
                })
                .error(self._handleError);
        };
        self._initializeForm();
    };

    list_exports.controller(exportsControllers);

}(window.angular));
