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

    download_export.constant('maxColumnSize', 2000);
    download_export.constant('defaultDateRange', null);
    download_export.constant('checkForMultimedia', false);

    var exportsControllers = {};
    exportsControllers.DownloadExportFormController = function (
        $scope, djangoRMI, exportList, maxColumnSize, exportDownloadService,
        defaultDateRange, checkForMultimedia, formElement
    ) {
        var self = {};
        $scope._ = _;   // make underscore.js available
        self._maxColumnSize = maxColumnSize;

        $scope.hasMultimedia = false;
        if (checkForMultimedia) {
            $.ajax({
                method: 'GET',
                url: hqImport("hqwebapp/js/initial_page_data").reverse("has_multimedia"),
                data: {
                    export_id: $scope.exportList[0].export_id,
                    form_or_case: hqImport('hqwebapp/js/initial_page_data').get("form_or_case"),
                },
                success: function (data) {
                    if (data.success) {
                        $scope.hasMultimedia = data.hasMultimedia;
                    }
                },
            });
        }

        $scope.formData.user_types = ['mobile'];
        $scope.formData['emw'] = hqImport('reports/js/reports.util').urlSerialize(
            $('form[name="exportFiltersForm"]'));
        if (formElement.user_type()) formElement.user_type().select2('val', ['mobile']);

        if (!_.isNull(defaultDateRange)) {
            $scope.formData.date_range = defaultDateRange;
        }

        if (exportType === 'case') {
            self.has_case_history_table = _.any($scope.exportList, function (export_) {
                return export_.has_case_history_table;
            });
        }

        $scope.isFormInvalid = function () {
            return _.isEmpty($scope.formData.user_types);
        };

        $scope.preparingMultimediaExport = false;
        $scope.prepareMultimediaExport = function () {
            $scope.prepareExportError = null;
            $scope.preparingMultimediaExport = true;
            $.ajax({
                method: 'POST',
                url: hqImport('hqwebapp/js/initial_page_data').reverse('prepare_form_multimedia'),
                data: {
                    form_or_case: hqImport('hqwebapp/js/initial_page_data').get("form_or_case"),
                    sms_export: hqImport('hqwebapp/js/initial_page_data').get("sms_export"),
                    exports: JSON.stringify($scope.exportList),
                    form_data: JSON.stringify($scope.formData),
                },
                success: function (data) {
                    if (data.success) {
                        self.sendAnalytics();
                        $scope.preparingMultimediaExport = false;
                        $scope.downloadInProgress = true;
                        exportDownloadService.startMultimediaDownload(data.download_id, self.exportType);
                    } else {
                        self._handlePrepareError(data);
                    }
                },
                error: self._handlePrepareError,
            });
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
            $scope.showError = false;
            $scope.celeryError = false;
            $scope.downloadError = false;
            $scope.isMultimediaDownload = false;
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

        $scope.$watch(function () {
        $scope.$watch(function () {
            return exportDownloadService.celeryError;
        }, function (status) {
            $scope.celeryError = status;
            $scope.showError = status;
        });

        $scope.$watch(function () {
            return exportDownloadService.downloadError;
        }, function (status) {
            $scope.downloadError = status;
            $scope.showError = status;
        });

        $scope.$watch(function () {
            return exportDownloadService.isMultimediaDownload;
        }, function (status) {
            $scope.isMultimediaDownload = status;
        });

    };
    download_export.controller(exportsControllers);

    var downloadExportServices = {};
    downloadExportServices.exportDownloadService = function ($interval, djangoRMI) {
        var self = {};


        self.startMultimediaDownload = function (downloadId, exportType) {
            self.isMultimediaDownload = true;
            self.startDownload(downloadId, exportType);
        };

        return self;
    };
    download_export.factory(downloadExportServices);

}(window.angular));
