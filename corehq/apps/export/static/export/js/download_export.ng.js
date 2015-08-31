(function (angular, undefined) {
    'use strict';
    // module: hq.download_export

    /* This is the helper module for the Download Exports Page. */

    var download_export = angular.module('hq.download_export', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages'
    ]);

    download_export.constant('exportList', []);

    var exportsControllers = {};
    exportsControllers.DownloadExportFormController = function (
        $scope, djangoRMI, exportList, exportDownloadService
    ) {
        var self = {};
        $scope._ = _;   // make underscore.js available
        $scope.formData = {};
        $scope.exportList = exportList;

        $scope.showSelectGroups = false;
        $scope.hasGroups = false;
        $scope.groupsLoading = true;
        $scope.groupsError = false;
        self._groupRetries = 0;

        self._handleGroupError = function () {
            $scope.groupsLoading = false;
            $scope.groupsError = true;
        };

        self._handleGroupRetry = function () {
            if (self._groupRetries > 3) {
                self._handleGroupError();
            } else {
                self._groupRetries ++;
                self._getGroups();
            }
        };

        self._updateGroups = function (data) {
            if (data.success) {
                $scope.groupsLoading = false;
                $scope.hasGroups = data.groups.length > 0;
                $('#id_groups').select2({
                    data: data.groups
                });
            } else {
                self._handleGroupRetry();
            }
        };

        self._getGroups = function () {
            djangoRMI.get_group_options({})
                .success(self._updateGroups)
                .error(self._handleGroupRetry);
        };

        self._getGroups();

        $scope.prepareExport = function () {
            exportDownloadService.startDownload($scope.exportList, $scope.formData);
        };
    };
    download_export.controller(exportsControllers);

    var downloadExportServices = {};
    downloadExportServices.exportDownloadService = function ($interval, djangoRMI) {
        var self = {};

        self.exportList = [];
        self.formData = {};

        self._numErrors = 0;

        self._testPolls = 0;

        self._checkDownloadProgress = function () {
            djangoRMI.check_export_prep({})
                .success(function (data) {
                    console.log('update');
                    self._testPolls ++;
                    if (self._testPolls > 10) {
                        $interval.cancel(self._promise);
                    }

                })
                .error(function () {
                    if (self._numErrors > 3) {
                        console.log('deal with error');
                    }
                    self._numErrors ++;
                });
        };

        self.startDownload = function (exportList, formData) {
            self.exportList = exportList;
            self.formData = formData;
            self._promise = $interval(self._checkDownloadProgress, 2000);
        };

        return self;
    };
    download_export.factory(downloadExportServices);

}(window.angular));
