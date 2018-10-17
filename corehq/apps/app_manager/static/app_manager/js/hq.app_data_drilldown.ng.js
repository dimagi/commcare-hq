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

        $scope.selectedAppData = {};
        $scope.$watch('formData.application', function (curAppId) {
        });

        $scope.selectedFormData = {};
        $scope.$watch('formData.form', function (curFormId) {
        });
    };
    app_drilldown.controller(selectControllers);

}(window.angular));
