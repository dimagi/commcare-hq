(function (angular, undefined) {
    'use strict';

    var mobileWorkers = angular.module('hq.mobile_workers', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi'
    ]);

    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        ERROR: 'error',
        SUCCESS: 'success'
    };

    var MobileWorker = function (data) {
        var self = this;
        self.creationStatus = STATUS.NEW;
        self.username = data.username;
        self.password = data.password;
        self.password2 = data.password2;
        self.domain = data.domain;

        self.isPending = function () {
            return self.creationStatus === STATUS.PENDING;
        };

        _.each(data.customFields, function (value, key) {
            self[key] = value;
        });
    };

    var mobileWorkerControllers = {};

    mobileWorkerControllers.newMobileWorkerFormController = function (
            $scope, workerCreationService
    ) {
        $scope.mobileWorker = {};
        $scope.initializeMobileWorker = function () {
            $scope.mobileWorker = new MobileWorker({});
        };
        $scope.submitNewMobileWorker = function () {
            workerCreationService.stageNewMobileWorker($scope.mobileWorker);
        };
    };

    mobileWorkerControllers.newMobileWorkerStatusController = function (
        $scope, workerCreationService
    ) {
        var showPending = function (worker) {
        };

        $scope.workers = [];
        $scope.$watch(
            function () {
                return workerCreationService.mobileWorkers;
            },
            function (newVal, oldVal) {
                $scope.workers = newVal;
            },
            true
        );
    };

    var mobileWorkerServices = {};

    mobileWorkerServices.workerCreationService = function (djangoRMI) {
        var self = {};
        self.mobileWorkers = [];

        self.stageNewMobileWorker = function (newWorker) {
            newWorker.creationStatus = STATUS.PENDING;
            self.mobileWorkers.push(newWorker);

            djangoRMI.create_mobile_worker({
                mobileWorker: newWorker
            })
            .success(function (data) {
                newWorker.creationStatus = STATUS.SUCCESS;
                // remove newWorker from pending, add to successful
            })
            .error();

            console.log("added to mobileWorkers");
        };

        return self;
    };

    mobileWorkers.service(mobileWorkerServices);

    mobileWorkers.controller(mobileWorkerControllers);
}(window.angular));
