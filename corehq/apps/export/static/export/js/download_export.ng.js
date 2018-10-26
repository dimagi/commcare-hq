(function (angular, undefined) {
    'use strict';
    // module: hq.download_export

    /* This is the helper module for the Download Exports Page. */

    var download_export = angular.module('hq.download_export', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages',
    ]);

    download_export.config(['$httpProvider', function ($httpProvider) {
        $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    download_export.constant('formElement', {
        progress: function () { return null; },
        group: function () { return null; },
        user_type: function () { return null; },
    });

    var exportsControllers = {};
    exportsControllers.DownloadExportFormController = function (
        $scope, djangoRMI, exportList, maxColumnSize, exportDownloadService,
    ) {
        var self = {};
        $scope._ = _;   // make underscore.js available

        $scope.formData.user_types = ['mobile'];
        $scope.formData['emw'] = hqImport('reports/js/reports.util').urlSerialize(
            $('form[name="exportFiltersForm"]'));
        if (formElement.user_type()) formElement.user_type().select2('val', ['mobile']);

        $scope.isFormInvalid = function () {
            return _.isEmpty($scope.formData.user_types);
        };

        $scope.$watch(function () {
            return exportDownloadService.showDownloadStatus;
        }, function (status) {
            $scope.downloadInProgress = status;
        });
        $scope.downloadInProgress = false;
    };

    exportsControllers.DownloadProgressController = function (
        $scope, exportDownloadService, formElement
    ) {
        var self = {};

        self._reset = function () {
            $scope.showProgress = false;
            $scope.showDownloadStatus = false;
            $scope.isDownloadReady = false;
            $scope.isDownloaded = false;
            $scope.dropboxUrl = null;
            $scope.downloadUrl = null;
            $scope.progress = {};
            if (formElement.progress()) {
                formElement.progress().css('width', '0%');
                formElement.progress().removeClass('progress-bar-success');
            }
        };

        self._reset();

        $scope.resetDownload = function () {
            self._reset();
            exportDownloadService.resetDownload();
        };
    };
    download_export.controller(exportsControllers);

}(window.angular));
