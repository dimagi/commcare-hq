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

        self.password = data.generateStrongPasswords ? generateStrongPassword() : '';

        self.isPending = function () {
            return self.creationStatus === STATUS.PENDING;
        };

        return self;
    };

    var mobileWorkerControllers = {};

    mobileWorkerControllers.mobileWorkerCreationController = function (
        $scope, djangoRMI, 
        generateStrongPasswords, $http
    ) {
        $scope._ = _;  // make underscore available
        $scope.mobileWorker = {};
        $scope.workers = [];
        $scope.generateStrongPasswords = generateStrongPasswords;

        $scope.markNonDefault = function () {
            visualFormCtrl.markNonDefault();
        };

        $scope.markDefault = function () {
            visualFormCtrl.markDefault();
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
}(window.angular));
