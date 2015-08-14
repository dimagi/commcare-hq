(function (angular, undefined) {
    'use strict';

    var mobileWorkers = angular.module('hq.mobile_workers', []);

    var MobileWorker = function (data) {
        var self = this;
        self.username = data.username;
        self.password = data.password;
        self.password2 = data.password2;
        self.domain = data.domain;

        _.each(data.customFields, function (value, key) {
            self[key] = value;
        });
    };

    var mobileWorkerControllers = {};

    mobileWorkerControllers.newMobileWorkerFormController = function ($scope) {
        $scope.mobileWorker = {};
        $scope.initializeMobileWorker = function (data) {
            console.log(data);
            $scope.mobileWorker = new MobileWorker(data);
        };
    };

    mobileWorkers.controller(mobileWorkerControllers);
}(window.angular));
