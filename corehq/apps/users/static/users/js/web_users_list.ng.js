(function (angular, undefined) {
    'use strict';
    // module: hq.web_users

    var users = angular.module('hq.web_users', [
        'ui.bootstrap',
        'ngResource',
        'ngRoute',
        'ng.django.rmi'
    ]);

    users.constant('webUsersConfig', {

    });

    var WebUser = function (data) {
        var self = {};
        self.email = data.email;
        self.name = data.name;
        self.role = data.role;
        self.phoneNumbers = data.phoneNumbers;
        self.removeMembershipUrl = data.removeMembershipUrl;
    };

    var usersControllers = {};
    usersControllers.paginatedListController = function($scope, djangoRMI) {
        var self = this;
        $scope.paginatedItems = [new WebUser({
                email: 'foo@bar.com',
                name: "Foo Bar",
                role: "Admin",
                phoneNumbers: ["+16175005454"],
                removeMembershipUrl: null
            })];
        $scope.limit = 10;
        $scope.total = 1;
        $scope.maxSize = 8;
        $scope.currentPage = 1;

        $scope.pageChanged = function () {
            console.log('change page');
        };
    };
    users.controller(usersControllers);

}(window.angular));
