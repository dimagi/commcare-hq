(function (angular, undefined) {
    'use strict';

    var pagination = angular.module('hq.pagination', [
        'ui.bootstrap',
        'ngResource',
        'ngRoute',
        'ng.django.rmi'
    ]);

    pagination.constant('paginationConfig', {
        transformSuccessItem: function (data) {
            // transforms data from the djangular endpoint
            return data;
        }
    });

    var paginationControllers = {};

    paginationControllers.paginatedListController = function($scope, djangoRMI, paginationConfig) {
        var self = this;
        $scope.paginatedItems = [];

        $scope.limit = 10;
        $scope.total = 1;
        $scope.maxSize = 8;
        $scope.currentPage = 1;

        $scope.query = '';

        $scope.error = null;
        $scope.notLoaded = true;

        self.retries = 0;

        self.updateList = function (data) {
            console.log(data);
            if (data.success) {
                $scope.paginatedItems = _.map(
                    data.response.itemList,
                    paginationConfig.transformSuccessItem
                );
                $scope.total = data.response.total;
                $scope.currentPage = data.response.page;
                $scope.query = data.response.query;
                if ($scope.notLoaded) {
                    $scope.notLoaded = false;
                }
            }
        };

        self.retry = function () {
            if (self.retries < 3) {
                self.retries ++;
                self.getData();
            } else {
                // TODO: show error
            }
        };

        self.getData = function () {
            djangoRMI.get_pagination_data({
                limit: $scope.limit,
                page: $scope.currentPage,
                query: $scope.query
            })
                .success(self.updateList)
                .error(self.retry);
        };

        $scope.pageChanged = function () {
            self.getData();
        };

        $scope.filterData = function () {
            self.getData();
        };

        $scope.updateQuery = function (keyEvent) {
            if (keyEvent.keyCode === 13) {
                self.getData();
            }
        };

        self.getData();
    };

    pagination.controller(paginationControllers);

}(window.angular));
