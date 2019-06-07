/* globals zxcvbn */
(function (angular) {
    'use strict';

    var mobileWorkers = angular.module('hq.mobile_workers', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi',
        'ngMessages', 
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
                .removeClass('has-error has-pending has-success has-warning');
        },
        usernameSuccess: function () {
            $formElements.username()
                .removeClass('has-error has-pending has-warning')
                .addClass('has-success');
        },
        usernameWarning: function () {
            $formElements.username()
                .removeClass('has-error has-pending has-success')
                .addClass('has-warning');
        },
        usernamePending: function () {
            $formElements.username()
                .removeClass('has-error has-success has-warning')
                .addClass('has-pending');
        },
        usernameError: function () {
            $formElements.username()
                .removeClass('has-success has-pending has-warning')
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
                    .text(gettext('Your password is almost strong enough! Try adding numbers or symbols!'));
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

    var USERNAME_STATUS = {
        PENDING: 'pending',
        TAKEN: 'taken',
        AVAILABLE: 'available',
        AVAILABLE_WARNING: 'warning',
        ERROR: 'error', 
    };

    mobileWorkers.constant('customFields', []);
    mobileWorkers.constant('customFieldNames', []);

    var mobileWorker = function (data) {
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

            var specials = '!@#$%^&*()_+{}:"<>?\|[];\',./`~';   // eslint-disable-line no-useless-escape
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

        var self = {};
        self.creationStatus = STATUS.NEW;

        self.username = data.username || '';
        self.firstName = data.first_name || '';
        self.lastName = data.last_name || '';
        self.editUrl = data.editUrl || '';
        self.locationId = data.location_id || '';

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

        return self;
    };

    var mobileWorkerControllers = {};

    mobileWorkerControllers.mobileWorkerCreationController = function (
        $scope, djangoRMI, customFields,
        customFieldNames, generateStrongPasswords, $http
    ) {
        $scope._ = _;  // make underscore available
        $scope.mobileWorker = {};
        $scope.usernameAvailabilityStatus = null;
        $scope.usernameStatusMessage = null;
        $scope.workers = [];
        $scope.customFormFields = customFields;
        $scope.customFormFieldNames = customFieldNames;
        $scope.generateStrongPasswords = generateStrongPasswords;

        $scope.markNonDefault = function () {
            visualFormCtrl.markNonDefault();
        };

        $scope.markDefault = function () {
            visualFormCtrl.markDefault();
        };

        $scope.initializeMobileWorker = function (existingMobileWorker) {
            visualFormCtrl.usernameClear();
            $scope.usernameAvailabilityStatus = null;
            $scope.usernameStatusMessage = null;

            if (!_.isEmpty(existingMobileWorker)) {
                mobileWorker.creationStatus = STATUS.RETRIED;
                $scope.mobileWorker = mobileWorker({
                    customFields: existingMobileWorker.customFields,
                    username: existingMobileWorker.username,
                });
            } else {
                $scope.mobileWorker = mobileWorker({
                    customFields: customFields,
                    generateStrongPasswords: generateStrongPasswords,
                });
            }
            hqImport('analytix/js/google').track.event('Manage Mobile Workers', 'New Mobile Worker', '');
        };

        $scope.retryMobileWorker = function (worker) {
            $scope.initializeMobileWorker(worker);
            $scope.usernameAvailabilityStatus = USERNAME_STATUS.AVAILABLE;
            $scope.usernameStatusMessage = gettext('Username is available.');
            $scope.markNonDefault();
        };
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
                            username: username, 
                        })
                            .success(function (data) {
                                if (data.success) {
                                    visualFormCtrl.usernameSuccess();
                                    $scope.usernameAvailabilityStatus = USERNAME_STATUS.AVAILABLE;
                                    deferred.resolve(data.success);
                                    $scope.usernameStatusMessage = data.success;
                                } else if (data.warning) {
                                    visualFormCtrl.usernameWarning();
                                    $scope.usernameAvailabilityStatus = USERNAME_STATUS.AVAILABLE_WARNING;
                                    deferred.resolve(data.warning);
                                    $scope.usernameStatusMessage = data.warning;
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
            },
        };
    };

    mobileWorkerDirectives.validatePasswordStandard = function () {
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
            },
        };
    };

    mobileWorkerDirectives.validatePasswordDraconian = function () {
        return {
            restrict: 'AE',
            require: 'ngModel',
            link: function ($scope, $elem, $attr, ctrl) {
                ctrl.$validators.validatePassword = function (password) {
                    if (!password) {
                        return false;
                    } else if (!(
                        password.length >= 8 &&
                        /\W/.test(password) &&
                        /\d/.test(password) &&
                        /[A-Z]/.test(password)
                    )) {
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

    mobileWorkers.directive(mobileWorkerDirectives);
    mobileWorkers.controller(mobileWorkerControllers);

    var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;
    var mobileWorkerApp = angular.module('mobileWorkerApp', ['hq.mobile_workers', 'ngSanitize', 'ui.select']);
    mobileWorkerApp.config(['$httpProvider', function ($httpProvider) {
        $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    mobileWorkerApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
        djangoRMIProvider.configure(initial_page_data('djng_current_rmi'));
    }]);
    mobileWorkerApp.constant('customFields', initial_page_data('custom_fields'));
    mobileWorkerApp.constant('generateStrongPasswords', initial_page_data('strong_mobile_passwords'));
}(window.angular));
