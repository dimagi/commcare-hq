hqDefine("data_interfaces/js/add_automatic_update_rule", function () {
    'use strict';
    var angular = window.angular,
        initial = hqImport("hqwebapp/js/initial_page_data").get('current_values'),
        autoUpdateRuleApp = angular.module('addUpdateRuleApp', ['ng.django.rmi']);

    autoUpdateRuleApp.config(['$httpProvider', function ($httpProvider) {
        $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);

    autoUpdateRuleApp.config(function (djangoRMIProvider) {
        djangoRMIProvider.configure(hqImport("hqwebapp/js/initial_page_data").get('djng_current_rmi'));
    });

    autoUpdateRuleApp.controller('UpdateRuleController', function ($scope, djangoRMI) {
        $scope.name = initial.name;
        $scope.case_type = initial.case_type;
        $scope.action = initial.action;
        $scope.update_property_name = initial.update_property_name;
        $scope.update_property_value = initial.update_property_value;
        $scope.server_modified_boundary = initial.server_modified_boundary;
        $scope.filter_on_server_modified = initial.filter_on_server_modified;
        $scope.property_value_type = initial.property_value_type;
        $scope.conditions_objs = initial.conditions;
        $scope.conditions = JSON.stringify(initial.conditions);
        $scope.case_property_map = {};

        $scope.get_typeahead_source = function (query, process) {
            process($scope.case_property_map[$scope.case_type] || []);
        };

        $scope.set_typeahead = function (element) {
            element.typeahead({
                source: $scope.get_typeahead_source,
                minLength: 0,
            });
        };

        $scope.init_typeahead = function () {
            $('.case-property-typeahead').each(function () {
                $scope.set_typeahead($(this));
            });
        };

        $scope.$watch('conditions_objs', function (newValue, oldValue) {
            $scope.conditions = JSON.stringify(newValue);
            if (newValue.length > oldValue.length) {
                setTimeout($scope.init_typeahead, 100);
            }
        }, true);

        $scope.showServerModifiedBoundaryField = function () {
            return $scope.filter_on_server_modified == 'true';
        };

        $scope.addCondition = function () {
            $scope.conditions_objs.push({});
            hqImport('analytix/js/google').track.event('Automatic Case Closure', 'Rules', 'Add Filter');
        };
        $scope.removeCondition = function (index) {
            $scope.conditions_objs.splice(index, 1);
            hqImport('analytix/js/google').track.event('Automatic Case Closure', 'Rules', 'Remove');
        };
        $scope.matchesDaysSince = function (condition) {
            return condition.property_match_type === 'DAYS' || condition.property_match_type === 'DAYS_BEFORE';
        };
        $scope.matchesHasValue = function (condition) {
            return condition.property_match_type == 'HAS_VALUE';
        };
        $scope.showUpdateProperty = function () {
            return $scope.action == 'UPDATE_AND_CLOSE' || $scope.action == 'UPDATE';
        };

        $(function () {
            djangoRMI.get_case_property_map().success(function (response) {
                if (response.success) {
                    $scope.case_property_map = response.data;
                }
            });
            $scope.init_typeahead();
        });
    });
});
