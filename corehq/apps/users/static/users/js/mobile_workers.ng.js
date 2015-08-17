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

    mobileWorkers.constant('formStrings', {
        checkingUsername: 'Checking username'
    });

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
            $scope, workerCreationService, djangoRMI, formStrings
    ) {
        $scope.mobileWorker = {};

        var $username_element = $('#id_username').parent();

        var clearStatus = function () {
            $scope.usernameAvailable = null;
            $scope.usernameTaken = null;
            $scope.usernamePending = null;
            $username_element.removeClass("has-warning has-error has-success");
        };

        $scope.initializeMobileWorker = function () {
            clearStatus();
            $scope.mobileWorker = new MobileWorker({});
        };

        $scope.submitNewMobileWorker = function () {
            workerCreationService.stageNewMobileWorker($scope.mobileWorker);
            $("#newMobileWorkerModal").modal('hide');
        };

        $scope.checkUsername = function () {
            clearStatus();
            $scope.usernamePending = formStrings.checkingUsername;
            $username_element.addClass("has-warning");
            djangoRMI.check_username({
                username: $scope.mobileWorker.username
            })
            .success(function (data) {
                clearStatus();
                if (!!data.success) {
                    $scope.usernameAvailable = data.success;
                    $username_element.addClass("has-success");
                } else {
                    $username_element.addClass("has-error");
                    $scope.usernameTaken = data.error;
                }
            })
            .error(function (data) {
                // TODO
                clearStatus();
                console.log(data);
            });
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
