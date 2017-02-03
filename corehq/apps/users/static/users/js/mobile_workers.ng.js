(function (angular, undefined) {
    'use strict';

    var mobileWorkers = angular.module('hq.mobile_workers', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages'
    ]);

    var $formElements = {
        username: function () {
            return $('#id_username').parent();
        },
        password: function () {
            return $('#id_password').parent();
        },
        passwordHint: function () {
            return $('#hint_id_password');
        },
    };

    var visualFormCtrl = {
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
        },
        passwordSuccess: function () {
            $formElements.password()
                .removeClass('has-error has-pending')
                .addClass('has-success');
            if ($formElements.password().hasClass('non-default')) {
                $formElements.passwordHint()
                    .text(gettext('Good Job! Your password is strong!'));
            }
        },
        passwordAlmost: function () {
            $formElements.password()
                .removeClass('has-error has-success')
                .addClass('has-pending');
            if ($formElements.password().hasClass('non-default')) {
                $formElements.passwordHint()
                    .text(gettext('Your password is almost strong enough!'));
            }
        },
        passwordError: function () {
            $formElements.password()
                .removeClass('has-success has-pending')
                .addClass('has-error');
            if ($formElements.password().hasClass('non-default')) {
                $formElements.passwordHint()
                    .text(gettext('Your password is too weak! Try adding numbers or symbols!'));
            }
        },
        markDefault: function () {
            $formElements.password()
                .removeClass('non-default')
                .addClass('default');
            $formElements.passwordHint().html(
                '<i class="fa fa-warning"></i>' +
                gettext('This password is automatically generated. Please copy it or create your own. It will not be shown again.') +
                ' <br />'
            );
        },
        markNonDefault: function () {
            $formElements.password()
                .removeClass('default')
                .addClass('non-default');
        },
    };

    var STATUS = {
        NEW: 'new',
        PENDING: 'pending',
        WARNING: 'warning',
        SUCCESS: 'success',
        RETRIED: 'retried'
    };

    var USERNAME_STATUS = {
        PENDING: 'pending',
        TAKEN: 'taken',
        AVAILABLE: 'available',
        ERROR: 'error'
    };

    mobileWorkers.constant('customFields', []);
    mobileWorkers.constant('customFieldNames', []);
    mobileWorkers.constant('location_url', '');

    var MobileWorker = function (data) {
        function generateStrongPassword() {
            function pick(possible, min, max) {
                var n, chars = '';

                if (typeof max === 'undefined') {
                    n = min;
                } else {
                    n = min + Math.floor(Math.random() * (max - min + 1));
                }

                for (var i = 0; i < n; i++) {
                    chars += possible.charAt(Math.floor(Math.random() * possible.length));
                }

                return chars;
            }

            function shuffle(password) {
                var array = password.split('');
                var tmp, current, top = array.length;

                if (top) while (--top) {
                    current = Math.floor(Math.random() * (top + 1));
                    tmp = array[current];
                    array[current] = array[top];
                    array[top] = tmp;
                }

                return array.join('');
            }

            var specials = '!@#$%^&*()_+{}:"<>?\|[];\',./`~';
            var lowercase = 'abcdefghijklmnopqrstuvwxyz';
            var uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
            var numbers = '0123456789';

            var all = specials + lowercase + uppercase + numbers;

            var password = '';
            password += pick(specials, 1);
            password += pick(lowercase, 1);
            password += pick(uppercase, 1);
            password += pick(numbers, 1);
            password += pick(all, 6, 10);
            return shuffle(password);
        }

        var self = this;
        self.creationStatus = STATUS.NEW;

        self.username = data.username || '';
        self.first_name = data.first_name || '';
        self.last_name = data.last_name || '';
        self.editUrl = data.editUrl || '';
        self.location_id = data.location_id || '';

        self.password = data.generateStrongPasswords ? generateStrongPassword() : '';

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
            $scope, workerCreationFactory, djangoRMI, customFields,
            customFieldNames, generateStrongPasswords, location_url, $http
    ) {
        $scope._ = _;  // make underscore available
        $scope.mobileWorker = {};
        $scope.usernameAvailabilityStatus = null;
        $scope.usernameStatusMessage = null;
        $scope.workers = [];
        $scope.customFormFields = customFields;
        $scope.customFormFieldNames = customFieldNames;
        $scope.generateStrongPasswords = generateStrongPasswords;

        $scope.markNonDefault = function (password) {
            visualFormCtrl.markNonDefault();
        };

        $scope.markDefault = function (password) {
            visualFormCtrl.markDefault();
        };

        $scope.availableLocations = [];

        $scope.searchLocations = function (query) {
            var reqStr = location_url + "?name=" + query;
            $http.get(reqStr).then(
                function (response) {
                    $scope.availableLocations = response.data;
                }
            );
        };

        $scope.initializeMobileWorker = function (mobileWorker) {
            visualFormCtrl.usernameClear();
            $scope.usernameAvailabilityStatus = null;
            $scope.usernameStatusMessage = null;

            if (!_.isEmpty(mobileWorker)) {
                mobileWorker.creationStatus = STATUS.RETRIED;
                $scope.mobileWorker = new MobileWorker({
                    customFields: mobileWorker.customFields,
                    username: mobileWorker.username
                });
            } else {
                $(".select2multiplechoicewidget").select2('data', null);
                $scope.mobileWorker = new MobileWorker({
                    customFields: customFields,
                    generateStrongPasswords: generateStrongPasswords,
                });
            }
            ga_track_event('Manage Mobile Workers', 'New Mobile Worker', '');
        };

        $scope.submitNewMobileWorker = function () {
            $("#newMobileWorkerModal").modal('hide');
            $scope.workers.push($scope.mobileWorker);
            workerCreationFactory.stageNewMobileWorker($scope.mobileWorker);
        };

        $scope.retryMobileWorker = function (worker) {
            $scope.initializeMobileWorker(worker);
            $scope.usernameAvailabilityStatus = USERNAME_STATUS.AVAILABLE;
            $scope.usernameStatusMessage = gettext('Username is available.');
            $scope.markNonDefault();
        };
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
                    newWorker.creationStatus = STATUS.WARNING;
                    deferred.reject(data);
                }
            })
            .error(function () {
                newWorker.creationStatus = STATUS.WARNING;
                deferred.reject(
                    gettext("Sorry, there was an issue communicating with the server.")
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
                                gettext("Sorry, there was an issue communicating with the server.")
                            );
                        });
                    }
                    return deferred.promise;
                };
            }
        };
    };

    mobileWorkerDirectives.validatePasswordStandard = function ($http, $q, djangoRMI) {
        return {
            restrict: 'AE',
            require: 'ngModel',
            link: function ($scope, $elem, $attr, ctrl) {
                ctrl.$validators.validatePassword = function (password) {
                    if (!password) {
                        return false;
                    }
                    var score = zxcvbn(password, ['dimagi', 'commcare', 'hq', 'commcarehq']).score,
                        goodEnough = score > 1;

                    if (goodEnough) {
                        visualFormCtrl.passwordSuccess();
                    } else if (score < 1) {
                        visualFormCtrl.passwordError();
                    } else {
                        visualFormCtrl.passwordAlmost();
                    }

                    return goodEnough;
                };
            }
        };
    };

    mobileWorkerDirectives.validatePasswordDraconian = function ($http, $q, djangoRMI) {
        return {
            restrict: 'AE',
            require: 'ngModel',
            link: function ($scope, $elem, $attr, ctrl) {
                ctrl.$validators.validatePassword = function (password) {
                    if (!password) {
                        return false;
                    }
                    $formElements.password()
                        .removeClass('has-error has-success')
                        .addClass('has-pending');
                    if ($formElements.password().hasClass('non-default')) {
                        $formElements.passwordHint()
                            .text(gettext(gettext("Password Requirements: 1 special character, " +
                                          "1 number, 1 capital letter, minimum length of 8 characters.")));
                    }

                    return true;
                };
            },
        };
    };

    mobileWorkerDirectives.validateLocation = function ($http, $q, djangoRMI) {
        return {
            restrict: 'AE',
            require: 'ngModel',
            link: function ($scope, $elem, $attr, ctrl) {
                ctrl.$validators.validateLocation = function (location_id) {
                    return !!location_id;
                };
            },
        };
    };

    mobileWorkers.directive(mobileWorkerDirectives);
    mobileWorkers.factory(mobileWorkerFactories);
    mobileWorkers.controller(mobileWorkerControllers);
}(window.angular));
