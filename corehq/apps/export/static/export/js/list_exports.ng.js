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

    list_exports.config(['$httpProvider', function($httpProvider) {
        $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
    }]);

    var exportsControllers = {};
    exportsControllers.ListExportsController = function (
        $scope, djangoRMI
    ) {
        /**
         * This controller fetches a list of saved exports from
         * subclasses of BaseExportListView.
         *
         * It also generates a list of exports selected for bulk exports.
         */

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
                        return;
                    }
                    self._numTries ++;
                    self._getExportsList();
                });
        };
        self._getExportsList();

        // For Bulk Export
        $scope.showBulkExportDownload = false;
        $scope.bulkExportList = '[]';

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
        $scope.sendExportAnalytics = function() {
            analytics.workflow("Clicked Export button");
        };
        $scope.updateEmailedExportData = function (component, exp) {
            $('#modalRefreshExportConfirm-' + exp.id + '-' + component.groupId).modal('hide');
            component.updatingData = true;
            djangoRMI.update_emailed_export_data({
                'component': component,
                'export': exp
            })
                .success(function (data) {
                    if (data.success) {
                        var exportType = _(exp.exportType).capitalize();
                        analytics.usage("Update Saved Export", exportType, "Saved");
                        component.updatingData = false;
                        component.updatedDataTriggered = true;
                    }
                });
        };
    };

    list_exports.controller(exportsControllers);

}(window.angular));
