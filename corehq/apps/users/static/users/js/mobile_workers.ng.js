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

    var mobileWorkerControllers = {};

    mobileWorkerControllers.mobileWorkerCreationController = function (
        $scope, djangoRMI, $http
    ) {
        $scope._ = _;  // make underscore available
        $scope.mobileWorker = {};
        $scope.workers = [];
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
