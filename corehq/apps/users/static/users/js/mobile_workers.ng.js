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
        AVAILABLE: 'available',
        ERROR: 'error'
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
        self.editUrl = data.editUrl || '';

        self.password = '';
        self.password_2 = '';

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
        $scope._ = _;  // make underscore available
        $scope.mobileWorker = {};
        $scope.usernameAvailabilityStatus = null;
        $scope.usernameStatusMessage = null;
        $scope.workers = [];
        $scope.customFormFields = customFields;
        $scope.customFormFieldNames = customFieldNames;

        $scope.initializeMobileWorker = function (mobileWorker) {
            visualFormCtrl.passwordClear();
            visualFormCtrl.usernameClear();
            $scope.usernameAvailabilityStatus = null;
            $scope.usernameStatusMessage = null;

            if (!!mobileWorker) {
                mobileWorker.creationStatus = USERNAME_STATUS.RETRIED;
                $scope.mobileWorker = new MobileWorker({
                    customFields: mobileWorker.customFields,
                    username: mobileWorker.username
                });
            } else {
                $(".select2multiplechoicewidget").select2('data', null);
                $scope.mobileWorker = new MobileWorker({customFields: customFields});
            }
        };

        $scope.submitNewMobileWorker = function () {
            $("#newMobileWorkerModal").modal('hide');
            $scope.workers.push($scope.mobileWorker);
            workerCreationFactory.stageNewMobileWorker($scope.mobileWorker)
                .then(
                    // success
                    function (data) {
                        // do nothing, the list handles it
                    },
                    // error
                    function (data) {
                        // do nothing, the list handles it
                    }
                );
        };

        $scope.hasPending = false;
        $scope.$watch(
            function(scope) {
                var pendingWorkers = _.filter(scope.workers, function (worker) {
                    return worker.creationStatus === STATUS.PENDING;
                });
                return pendingWorkers.length > 0;
            },
            function (newVal) {
                $scope.hasPending = newVal;
            }
        );

        $scope.hasSuccess = false;
        $scope.$watch(
            function(scope) {
                var successWorkers = _.filter(scope.workers, function (worker) {
                    return worker.creationStatus === STATUS.SUCCESS;
                });
                return successWorkers.length > 0;
            },
            function (newVal) {
                $scope.hasSuccess = newVal;
            }
        );

        $scope.hasError = false;
        $scope.$watch(
            function(scope) {
                var errorWorkers = _.filter(scope.workers, function (worker) {
                    return worker.creationStatus === STATUS.ERROR;
                });
                return errorWorkers.length > 0;
            },
            function (newVal) {
                $scope.hasError = newVal;
            }
        );

    };

    var mobileWorkerFactories = {};
    mobileWorkerFactories.workerCreationFactory = function ($q, djangoRMI) {
        var self = {};

        self.stageNewMobileWorker = function (newWorker) {
            newWorker.creationStatus = STATUS.PENDING;
            var deferred = $q.defer();
            djangoRMI.create_mobile_worker({
                mobileWorker: newWorker
            })
            .success(function (data) {
                if (data.success) {
                    newWorker.creationStatus = STATUS.SUCCESS;
                    newWorker.editUrl = data.editUrl;
                    deferred.resolve(data);
                } else {
                    newWorker.creationStatus = STATUS.SUCCESS;
                    deferred.reject(data);
                }
            })
            .error(function () {
                newWorker.creationStatus = STATUS.ERROR;
                deferred.reject(
                    "Sorry, there was an issue communicating with the server."
                );
            });

            return deferred.promise;
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
                                deferred.resolve(data.success);
                                $scope.usernameStatusMessage = data.success;
                            } else {
                                visualFormCtrl.usernameError();
                                $scope.usernameAvailabilityStatus = USERNAME_STATUS.TAKEN;
                                deferred.reject(data.error);
                                $scope.usernameStatusMessage = data.error;
                            }
                        })
                        .error(function () {
                            $scope.usernameAvailabilityStatus = USERNAME_STATUS.ERROR;
                            deferred.reject(
                                "Sorry, there was an issue communicating with the server."
                            );
                        });
                    }
                    return deferred.promise;
                };
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
