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
    });

    var exportsControllers = {};
    exportsControllers.DownloadExportFormController = function (
        $scope, djangoRMI, exportList, maxColumnSize, exportDownloadService,
    ) {
        var self = {};
        $scope._ = _;   // make underscore.js available

        $scope.formData['emw'] = hqImport('reports/js/reports.util').urlSerialize(
            $('form[name="exportFiltersForm"]'));
    };

    exportsControllers.DownloadProgressController = function (
        $scope, exportDownloadService, formElement
    ) {
        var self = {};
    };
    download_export.controller(exportsControllers);

}(window.angular));
