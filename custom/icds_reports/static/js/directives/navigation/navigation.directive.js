/* global _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function NavigationController($window, $rootScope, $scope, $route, $routeParams, $location, stateLevelAccess, haveAccessToAllLocations, haveAccessToFeatures) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.stateLevelAccess = stateLevelAccess;
    $scope.haveAccessToAllLocations = haveAccessToAllLocations;
    $scope.haveAccessToFeatures = haveAccessToFeatures;

    var checkColapse = function(reports) {
        var path = _.filter(reports, function(report) { return $location.path().indexOf(report) !== -1; });
        return !path.length > 0;
    };

    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = checkColapse(['underweight_children', 'wasting', 'stunting', 'low_birth', 'early_initiation', 'exclusive_breastfeeding', 'children_initiated', 'institutional_deliveries', 'immunization_coverage']);
    $scope.icdsCasReach = checkColapse(['awc_daily_status', 'awcs_covered']);
    $scope.demographics = checkColapse(['registered_household', 'enrolled_children', 'enrolled_women', 'lactating_enrolled_women', 'adolescent_girls', 'adhaar']);
    $scope.infrastructure = checkColapse(['clean_water', 'functional_toilet', 'medicine_kit', 'infants_weight_scale', 'adult_weight_scale']);

    $scope.goto = function(path) {
        $window.location.href = path;
    };

    $scope.goToStep = function(path, params) {
        var page_path = "#/" + path;
        if (Object.keys(params).length > 0) {
            page_path += '?';
        }

        window.angular.forEach(params, function(v, k) {
            if (v === undefined || v === null) {
                v = '';
            }
            page_path += (k + '=' + v + '&');
        });
        return page_path;
    };
}

NavigationController.$inject = ['$window', '$rootScope', '$scope', '$route', '$routeParams', '$location', 'stateLevelAccess', 'haveAccessToAllLocations', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive('navigation', function() {
    return {
        restrict: 'E',
        scope: {},
        controller: NavigationController,
        controllerAs: '$ctrl',
        templateUrl: url('icds-ng-template', 'navigation.directive'),
    };
});
