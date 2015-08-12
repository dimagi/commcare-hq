(function (angular, undefined) {
    'use strict';

    var users = angular.module('hq.mobile_workers', []);

    var MobileWorker = function (data) {
        var self = this;
        self.email = data.email;
        self.name = data.name;
        self.role = data.role;
        self.phoneNumbers = data.phoneNumbers;
        self.removeUrl = data.removeUrl;
        self.editUrl = data.editUrl;
        self.domain = data.domain;
    };

}(window.angular));
