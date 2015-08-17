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
    mobileWorkers.constant('customFields', []);

    var MobileWorker = function (data) {
        var self = this;
        self.creationStatus = STATUS.NEW;

        self.fields = {
            username: data.username || '',
            password: data.password || '',
            password2: data.password2 || '',
        };

        self.isPending = function () {
            return self.creationStatus === STATUS.PENDING;
        };

        _.each(data.customFields, function (key) {
            self.fields[key] = '';
        });
    };

    var mobileWorkerControllers = {};

    mobileWorkerControllers.newMobileWorkerFormController = function (
            $scope, workerCreationService, djangoRMI, formStrings, customFields
    ) {
        $scope.mobileWorker = {};

        var $usernameElement = $('#id_username').parent();
        var $passwordElement = $('#id_password_2').parent();

        var clearUsernameStatus = function () {
            $scope.usernameAvailable = null;
            $scope.usernameTaken = null;
            $scope.usernamePending = null;
            $usernameElement.removeClass("has-warning has-error has-success");
        };

        $scope.initializeMobileWorker = function () {
            clearUsernameStatus();
            $passwordElement.removeClass("has-error has-success");
            $scope.isPasswordValid = true;
            $(".select2multiplechoicewidget").select2('data', null);
            $scope.mobileWorker = new MobileWorker({customFields: customFields});
        };

        $scope.submitNewMobileWorker = function () {
            workerCreationService.stageNewMobileWorker($scope.mobileWorker);
            $("#newMobileWorkerModal").modal('hide');
        };

        $scope.checkUsername = function () {
            clearUsernameStatus();
            $scope.usernamePending = formStrings.checkingUsername;
            $usernameElement.addClass("has-warning");
            djangoRMI.check_username({
                username: $scope.mobileWorker.fields.username
            })
            .success(function (data) {
                clearUsernameStatus();
                if (!!data.success) {
                    $scope.usernameAvailable = data.success;
                    $usernameElement.addClass("has-success");
                } else {
                    $usernameElement.addClass("has-error");
                    $scope.usernameTaken = data.error;
                }
            })
            .error(function (data) {
                // TODO
                clearUsernameStatus();
                console.log(data);
            });
        };

        $scope.checkPassword = function () {
            if ($scope.mobileWorker.fields.password !== $scope.mobileWorker.fields.password2) {
                $scope.isPasswordValid = false;
                $passwordElement
                    .removeClass("has-success")
                    .addClass("has-error");
            } else {
                $scope.isPasswordValid = true;
                $passwordElement
                    .removeClass("has-error")
                    .addClass("has-success");
            }
        };

        $scope.validateForm = function () {
            var areFieldsSet = _.every($scope.mobileWorker.fields, function (val, key) {
                return !_.isEmpty(val);
            });
            return areFieldsSet && $scope.isPasswordValid && !!$scope.usernameAvailable;
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
                mobileWorker: newWorker.fields
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
