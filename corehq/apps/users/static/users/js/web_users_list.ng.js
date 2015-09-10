(function (angular, undefined) {
    'use strict';
    // module: hq.web_users

    var users = angular.module('hq.web_users', [
        'ui.bootstrap',
        'ngResource',
        'ngRoute',
        'ng.django.rmi'
    ]);

    var WebUser = function (data) {
        var self = this;
        self.id = data.id;
        self.email = data.email;
        self.name = data.name;
        self.role = data.role;
        self.phoneNumbers = data.phoneNumbers;
        self.removeUrl = data.removeUrl;
        self.editUrl = data.editUrl;
        self.domain = data.domain;
    };

    var usersControllers = {};
    usersControllers.paginatedListController = function($scope, djangoRMI) {
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

        self.updateUserList = function (data) {
            if (data.success) {
                $scope.paginatedItems = _.map(data.response.users, function (user_data) {
                    return new WebUser(user_data);
                });
                $scope.total = data.response.total;
                $scope.currentPage = data.response.page;
                $scope.query = data.response.query;
                if ($scope.notLoaded) {
                    $scope.notLoaded = false;
                }
            }
        };

        self.retry = function () {
            if (self.retries < 10) {
                self.retries ++;
                self.getUsers();
            } else {
                // show error
            }
        };

        self.getUsers = function () {
            djangoRMI.get_users({
                limit: $scope.limit,
                page: $scope.currentPage,
                query: $scope.query
            })
                .success(self.updateUserList)
                .error(self.retry);
        };
        self.getUsers();

        $scope.pageChanged = function () {
            self.getUsers();
        };

        $scope.filterUsers = function () {
            self.getUsers();
        };
    };
    users.controller(usersControllers);

}(window.angular));
