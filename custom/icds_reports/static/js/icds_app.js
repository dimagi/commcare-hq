var icdsApp = angular.module('icdsApp', ['ngRoute']);
icdsApp.config(function($routeProvider) {
    $routeProvider
    .when("/", {
        template : "icds_reports/icds_app/system_usage.html"
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
        template : "underweight_children"
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