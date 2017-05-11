angular.module('icdsApp', ['ngRoute', 'ui.select', 'ngSanitize', 'datamaps', 'ui.bootstrap'])
    .controller('MainController', function($scope, $route, $routeParams, $location) {
         $scope.$route = $route;
         $scope.$location = $location;
         $scope.$routeParams = $routeParams;
     })
    .config(function($routeProvider) {
        var url = hqImport('hqwebapp/js/urllib.js').reverse;
        $routeProvider
        .when("/", {
            templateUrl : url('icds-ng-template', 'system_usage'),
            controller: "SystemUsageController",
            controllerAs: "$ctrl"
        })
        .when("/awc_opened", {
            template : "awc_opened"
        })
        .when("/active_awws", {
            template : "active_awws"
        })
        .when("/submitted_yesterday", {
            template : "submitted_yesterday"
        })
        .when("/submitted", {
            template : "submitted"
        })
        .when("/system_usage_tabular", {
            template : "system_usage_tabular"
        })
        .when("/underweight_children", {
            template : "<underweight-children-report></underweight-children-report>",
        })
        .when("/breastfeeding", {
            template : "breastfeeding"
        })
        .when("/exclusive_bf", {
            template : "exclusive_bf"
        })
        .when("/comp_feeding", {
            template : "comp_feeding"
        })
        .when("/health_tabular_report", {
            template : "health_tabular_report"
        });
    });