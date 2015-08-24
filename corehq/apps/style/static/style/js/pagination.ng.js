(function (angular, undefined) {
    'use strict';

    var pagination = angular.module('hq.pagination', [
        'ui.bootstrap',
        'ngResource',
        'ngRoute',
        'ng.django.rmi'
    ]);

    pagination.constant('paginationLimits', [
        [10, "Limit 10"]
    ]);

    pagination.constant("paginationCustomData", {});

    var paginationControllers = {};

    paginationControllers.PaginatedListController = function(
        $scope, djangoRMI, paginationConfig, paginationLimits,
        paginationCustomData
    ) {
        var self = this;
        $scope.paginatedItems = [];

        $scope.paginationLimits = _.map(paginationLimits, function (l) {
            return {
                value: l[0],
                key: l[1]
            }
        });
        $scope.limit = 10;
        $scope.total = 1;
        $scope.maxSize = 8;
        $scope.currentPage = 1;

        $scope.query = '';

        $scope.notLoaded = true;
        $scope.hasError = false;

        self.retries = 0;

        _.each(paginationCustomData, function (val, key) {
            $scope[key] = val;
        });

        self.updateList = function (data) {
            console.log(data);
            if (data.success) {
                $scope.paginatedItems = data.response.itemList;
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
                $scope.hasError = true;
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
