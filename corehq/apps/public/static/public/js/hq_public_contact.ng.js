(function (angular, undefined) {
    'use strict';
    // module: hq.public.contact
    var contact = angular.module('hq.public.contact', [
        'ngResource',
        'ngRoute',
        'ng.django.rmi'
    ]);

    var contactControllers = {};
    contactControllers.contactFormValidationController = function ($scope, djangoRMI) {
        $scope.master = {};
        var self = {};

        self.showSuccessMessage = function (resp) {
            // todo: success message
            console.log('success');
            console.log(resp);
        };

        self.showErrorMessage = function () {
            // todo: error message
            console.log('error');
        };

        $scope.send_email = function(contact) {
            $scope.master = angular.copy(contact);

            // todo: add in validation
            djangoRMI.send_email(contact).success(
                self.showSuccessMessage
            ).error(self.showErrorMessage);
        };

        $scope.reset = function() {
            $scope.contact = angular.copy($scope.master);
        };

        $scope.reset();
    };
    contact.controller(contactControllers);

}(window.angular));
