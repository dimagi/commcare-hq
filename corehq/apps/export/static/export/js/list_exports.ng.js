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
        $scope, djangoRMI, bulk_download_url, legacy_bulk_download_url, $rootScope
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
        $scope.bulk_download_url = bulk_download_url;
        $scope.legacy_bulk_download_url = legacy_bulk_download_url;

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
            var input = $('input[name="export_list"]');
            input.val(JSON.stringify(selectedExports));

            var useLegacyBulkExportUrl = _.every(selectedExports, function (e) {
                return e.isLegacy;
            });
            var currentUrl = useLegacyBulkExportUrl ? $scope.legacy_bulk_download_url : $scope.bulk_download_url;
            input.closest("form").attr("action", currentUrl);
        };
        $scope.downloadRequested = function($event) {
            var $btn = $($event.target);
            $btn.addClass('disabled');
            $btn.text(gettext('Download Requested'));
        };
        $scope.copyLinkRequested = function($event, export_) {
            export_.showLink = true;
            var clipboard = new Clipboard($event.target, {
                target: function (trigger) {
                    return trigger.nextElementSibling;
                }
            });
            clipboard.onClick($event);
            clipboard.destroy();
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
            $('#modalRefreshExportConfirm-' + exp.id + '-' + (component.groupId ? component.groupId : '')).modal('hide');
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
        $scope.setFilterModalExport = function (export_) {
            // The filterModalExport is used as context for the FeedFilterFormController
            $rootScope.filterModalExport = export_;
        };
    };
    exportsControllers.FeedFilterFormController = function (
        $scope, $rootScope, djangoRMI, filterFormElements, filterFormModalElement
    ) {
        var self = {};
        $scope._ = _;   // make underscore.js available
        $scope.formData = {};
        $scope.isSubmittingForm = false;
        $scope.hasFormSubmitError = false;
        $scope.formSubmitErrorMessage = null;

        var formElement = filterFormElements;
        $scope.hasGroups = true;

        $rootScope.$watch("filterModalExport", function (newSelectedExport, oldSelectedExport) {
            if (newSelectedExport) {
                $scope.formData = newSelectedExport.emailedExport.filters;
                // select2s require programmatic update
                formElement.user_type().select2("val", $scope.formData.user_types);
                formElement.group().select2("val", $scope.formData.group);
            }
        });

        $scope.$watch("formData.date_range", function(newDateRange, oldDateRange) {
            if (!newDateRange) {
                $scope.formData.date_range = "last7";
            }
        });
        $scope.$watch("formData.type_or_group", function(newVal, oldVal) {
            if (!newVal) {
                $scope.formData.type_or_group = "type";
            }
        });

        $scope.commitFilters = function () {
            var export_ = $rootScope.filterModalExport;
            $scope.isSubmittingForm = true;

            djangoRMI.commit_filters({
                export: export_,
                form_data: $scope.formData,
            }).success(function (data) {
                $scope.isSubmittingForm = false;
                if (data.success) {
                    self._clearSubmitError();
                    export_.emailedExport.filters = $scope.formData;
                    export_.emailedExport.updatingData = false;
                    export_.emailedExport.updatedDataTriggered = true;
                    filterFormModalElement().modal('hide');
                } else {
                    self._handleSubmitError(data);
                }
            }).error(function (data) {
                $scope.isSubmittingForm = false;
                self._handleSubmitError(data);
            });
        };

        self._handleSubmitError = function(data) {
            $scope.hasFormSubmitError = true;
            $scope.formSubmitErrorMessage = data.error;
        };
        self._clearSubmitError = function() {
            $scope.hasFormSubmitError = false;
            $scope.formSubmitErrorMessage = null;
        };
    };

    list_exports.controller(exportsControllers);

}(window.angular));
