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
        'ngMessages',
    ]);

    // defaults
    app_drilldown.constant('djangoRMICallbackName', 'submit_app_data_drilldown_form');
    app_drilldown.constant('processApplicationDataFormSuccessCallback', function (data) {
        console.log('success');
        console.log(data);
    });
    app_drilldown.constant('formModalSelector', null);

    var selectControllers = {};
    selectControllers.DrilldownToFormController = function (
        $scope, djangoRMI, formFieldSlugs, formDefaults, djangoRMICallbackName,
        processApplicationDataFormSuccessCallback, formModalSelector, staticModelType, modelType
    ) {
        var self = this;
        $scope._ = _;  // use underscore.js in templates

        $scope.staticModelType = staticModelType;

        $scope.showNoAppsError = false;

        $scope.hasSpecialAppTypes = false;
        $scope.hasNoCaseTypes = false;

        $scope.isSubmittingForm = false;
        $scope.formSubmissionError = null;

        $scope.formData = formDefaults;
        if (modelType) {
            $scope.formData['model_type'] = modelType;
        }

        $scope.resetForm = function () {
            util.setAppTypes();
            util.setApps(self._apps_by_type.all || []);
            util.setModules();
            util.setForms();
            util.setCaseTypes();
            $scope.selectedAppData = {};
            $scope.selectedFormData = {};
            $scope.hasNoCaseTypes = false;
        };

        if (formModalSelector) {
            $(formModalSelector).on('hidden.bs.modal', function () {
                $scope.resetForm();
            });
            $(formModalSelector).on('show.bs.modal', function () {
                hqImport('analytix/js/kissmetrix').track.event("Clicked New Export");
            });
        }


        $scope.handleSubmitForm = function () {
            $scope.isSubmittingForm = true;

            // Immediately copy form data object so that if modal is
            // accidentally dismissed, data is still properly sent
            var formData = _.clone($scope.formData);

            djangoRMI[djangoRMICallbackName]({
                formData: formData,
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
        });

        $scope.selectedFormData = {};
        $scope.$watch('formData.form', function (curFormId) {
        });
    };
    app_drilldown.controller(selectControllers);

}(window.angular));
