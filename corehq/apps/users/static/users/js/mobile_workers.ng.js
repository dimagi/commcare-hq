(function (angular, undefined) {
    'use strict';

    var mobileWorkers = angular.module('hq.mobile_workers', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages'
    ]);

    var $formElements = {
        password: function () {
            return $('#id_password_2').parent();
        },
        username: function () {
            return $('#id_username').parent();
        }
    };

    var visualFormCtrl = {
        passwordClear : function () {
            $formElements.password()
                .removeClass('has-error has-success');
        },
        passwordSuccess: function () {
            $formElements.password()
                .removeClass('has-error')
                .addClass('has-success');
        },
        passwordError: function () {
            $formElements.password()
                .removeClass('has-success')
                .addClass('has-error');
        },
        usernameClear: function () {
            $formElements.username()
                .removeClass('has-error has-pending has-success');
        },
        usernameSuccess: function () {
            $formElements.username()
                .removeClass('has-error has-pending')
                .addClass('has-success');
        },
        usernamePending: function () {
            $formElements.username()
                .removeClass('has-error has-success')
                .addClass('has-pending');
        },
        usernameError: function () {
            $formElements.username()
                .removeClass('has-success has-pending')
                .addClass('has-error');
        }
    };

    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        ERROR: 'error',
        SUCCESS: 'success',
        RETRIED: 'retried'
    };

    var USERNAME_STATUS = {
        PENDING: 'pending',
        TAKEN: 'taken',
        AVAILABLE: 'available'
    };

    mobileWorkers.constant('formStrings', {
        checkingUsername: 'Checking username'
    });
    mobileWorkers.constant('customFields', []);
    mobileWorkers.constant('customFieldNames', []);

    var MobileWorker = function (data) {
        var self = this;
        self.creationStatus = STATUS.NEW;

        self.username = data.username || '';
        self.userId = data.user_id || '';
        self.archiveStatus = data.status || '';
        self.editUrl = data.editUrl || '';

        self.password = '';
        self.password2 = '';
        self.customFields = {};

        self.isPending = function () {
            return self.creationStatus === STATUS.PENDING;
        };

        if (_.isArray(data.customFields)) {
            _.each(data.customFields, function (key) {
                self.customFields[key] = '';
            });
        } else if (_.isObject(data.customFields)) {
            self.customFields = data.customFields;
        }
    };

    var mobileWorkerControllers = {};

    mobileWorkerControllers.MobileWorkerCreationController = function (
            $scope, workerCreationFactory, djangoRMI, formStrings, customFields,
            customFieldNames
    ) {
        $scope.mobileWorker = {};
        $scope.usernameAvailabilityStatus = null;
        $scope.customFormFields = customFields;
        $scope.customFormFieldNames = customFieldNames;

        $scope.initializeMobileWorker = function () {
            visualFormCtrl.passwordClear();
            visualFormCtrl.usernameClear();
            $scope.usernameAvailabilityStatus = null;

            // clears select 2 widget from old data
            $(".select2multiplechoicewidget").select2('data', null);

            // initialize mobile worker model
            $scope.mobileWorker = new MobileWorker({customFields: customFields});
        };

        $scope.submitNewMobileWorker = function () {
            workerCreationService.stageNewMobileWorker($scope.mobileWorker);
            $("#newMobileWorkerModal").modal('hide');
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

    var mobileWorkerDirectives = {};
    mobileWorkerDirectives.validateUsername = function ($http, $q, djangoRMI) {
        return {
            restrict: 'AE',
            require: 'ngModel',
            link: function ($scope, $elem, $attr, ctrl) {
                ctrl.$validators.validateUsername = function (username) {
                    var deferred = $q.defer();
                    if (_.isUndefined(username) || _.isEmpty(username)) {
                        $scope.usernameAvailabilityStatus = null;
                        deferred.resolve();
                        visualFormCtrl.usernameClear();
                    } else {
                        $scope.usernameAvailabilityStatus = USERNAME_STATUS.PENDING;
                        visualFormCtrl.usernamePending();
                        djangoRMI.check_username({
                            username: username
                        })
                        .success(function (data) {
                            if (!!data.success) {
                                visualFormCtrl.usernameSuccess();
                                $scope.usernameAvailabilityStatus = USERNAME_STATUS.AVAILABLE;
                                deferred.resolve();
                            } else {
                                visualFormCtrl.usernameError();
                                $scope.usernameAvailabilityStatus = USERNAME_STATUS.TAKEN;
                                deferred.reject();
                            }
                        })
                        .error(function (data) {
                            deferred.reject();
                        });
                    }
                    return deferred.promise;
                }
            }
        };
    };
    mobileWorkerDirectives.confirmPassword = function ($q) {
        return {
            restrict: 'AE',
            require: 'ngModel',
            link: function ($scope, $attr, $elem, ctrl) {
                ctrl.$validators.confirmPassword = function (modelValue) {
                    var isConfirmed = $scope.mobileWorker.password === modelValue;
                    if (_.isUndefined(modelValue) || _.isEmpty(modelValue)) {
                        visualFormCtrl.passwordClear();
                    } else if (isConfirmed) {
                        visualFormCtrl.passwordSuccess();
                    } else {
                        visualFormCtrl.passwordError();
                    }
                    return isConfirmed;
                };
            }
        };
    };

    mobileWorkers.directive(mobileWorkerDirectives);
    mobileWorkers.factory(mobileWorkerFactories);
    mobileWorkers.controller(mobileWorkerControllers);
    
}(window.angular));
