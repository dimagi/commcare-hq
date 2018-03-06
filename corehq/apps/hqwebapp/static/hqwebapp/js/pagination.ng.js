(function (angular, undefined) {
    'use strict';

    var pagination = angular.module('hq.pagination', [
        'ui.bootstrap',
        'ngResource',
        'ngRoute',
        'ngCookies',
        'ng.django.rmi',
    ]);

    pagination.constant('paginationLimits', [
        [10, "Limit 10"],
    ]);

    pagination.constant('paginationLimitCookieName', 'hq.ngPaginationLimit');

    pagination.constant("paginationCustomData", {});

    var paginationControllers = {};

    paginationControllers.PaginatedListController = function(
        $scope, djangoRMI, paginationConfig, paginationLimits,
        paginationCustomData, paginationLimitCookieName, $cookies
    ) {
        var self = this;
        $scope._ = _;  // makes underscore available
        $scope.djangoRMI = djangoRMI;
        $scope.paginatedItems = [];

        $scope.paginationLimits = _.map(paginationLimits, function (l) {
            return {
                value: l[0],
                key: l[1],
            };
        });

        var storedLimit = $cookies.get(paginationLimitCookieName);
        if (_.isString(storedLimit)) {
            try {
                storedLimit = parseInt(storedLimit);
            } catch (e) {
                // do nothing
            }
        }
        if (!_.isNumber(storedLimit)) {
            storedLimit = 10;
        }
        $scope.limit = storedLimit;
        $scope.maxSize = 8;

        $scope.total = 1;
        $scope.currentPage = 1;

        $scope.query = '';

        $scope.notLoaded = true;
        $scope.hasError = false;

        self.retries = 0;

        $scope.paginationCustomData = paginationCustomData;
        _.each(paginationCustomData, function (val, key) {
            $scope[key] = val;
        });

        self.updateList = function (data) {
            if (data.success) {
                $scope.paginatedItems = data.response.itemList;
                $scope.total = data.response.total;
                $scope.currentPage = data.response.page;
                $scope.query = data.response.query;
                $scope.total_records = data.response.total_records;
                $cookies.put(paginationLimitCookieName, $scope.limit);
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
            var paginationData = {
                limit: $scope.limit,
                page: $scope.currentPage,
                query: $scope.query,
            };
            _.each($scope.paginationCustomData, function (val, key) {
                paginationData[key] = $scope[key];
            });
            djangoRMI.get_pagination_data(paginationData)
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
