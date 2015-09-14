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
        $scope.showBulkExportDownload = false;

        $scope.updateBulkStatus = function () {
            $scope.showBulkExportDownload = _.any($scope.exports, function (exp) {
                return !!exp.addedToBulk;
            })
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

        djangoRMI.get_exports_list({})
            .success(function (data) {
                if (data.success) {
                    $scope.exports = data.exports;
                    $scope.hasLoaded = true;
                } else {
                    // todo deal with error
                }
            })
            .error(function () {
                // todo deal with error
            });
    };

    exportsControllers.CreateFormExportController = function (
        $scope, djangoRMI
    ) {
        var self = {};
        $scope._ = _;  // use underscore.js in templates
        $scope.showNoAppsError = false;
        $scope.formLoadError = null;
        $scope.isLoaded = false;

        var $formElem = {
            get_app: function () {
                return $('#id_application');
            },
            get_module: function () {
                return $('#id_module');
            },
            get_form: function () {
                return $('#id_form');
            }
        };
        $scope.createForm = {
            application: '',
            module: '',
            form: ''
        };
        self._placeholders = {};
        self._modules = {};
        self._forms = {};

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
                $formElem.get_module().select2({
                    data: module_data || [],
                    triggerChange: true
                }).select2('val', null).trigger('change');
                $('#s2id_id_module')
                    .find('.select2-choice').addClass('select2-default')
                    .find('.select2-chosen').text(self._placeholders.module);
            },
            setForms: function (form_data) {
                $scope.createForm.form = '';
                $formElem.get_form().select2({
                    data: form_data || [],
                    triggerChange: true
                }).select2('val', null).trigger('change');
                $('#s2id_id_form')
                    .find('.select2-choice').addClass('select2-default')
                    .find('.select2-chosen').text(self._placeholders.form);
            }
        };

        $('#createExportOptionsModal').on('hide.bs.modal', function () {
            $formSelect.clearApp();
            $formSelect.setModules();
            $formSelect.setForms();
        });

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

        $scope.handleCreateFormExport = function () {
            console.log('create export');
            console.log($scope.createForm);
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
                            self._placeholders = data.placeholders;
                            $formSelect.setApps(data.apps);
                            $formSelect.setModules();
                            $formSelect.setForms();
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
