/* global _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function NavigationController($window, $rootScope, $scope, $route, $routeParams, $location, navigationService,
                              stateLevelAccess, haveAccessToAllLocations, haveAccessToFeatures,
                              userFullName, userUsername, isMobile, navMenuItems, $uibModal, reportAnIssueUrl,
                              isWebUser) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.stateLevelAccess = stateLevelAccess;
    $scope.haveAccessToAllLocations = haveAccessToAllLocations;
    $scope.haveAccessToFeatures = haveAccessToFeatures;
    $scope.userFullName = userFullName;
    $scope.userUsername = userUsername;
    $scope.expandedSectionId = '';
    $scope.navMenuItems = navMenuItems;
    $scope.isWebUser = isWebUser;

    var checkCollapse = function (reports) {
        var path = _.filter(reports, function (report) {
            return $location.path().indexOf(report) !== -1; 
        });
        return !path.length > 0;
    };

    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = checkCollapse(['underweight_children', 'wasting', 'stunting', 'low_birth', 'early_initiation', 'exclusive_breastfeeding', 'children_initiated', 'institutional_deliveries', 'immunization_coverage']);
    $scope.icdsCasReach = checkCollapse(['awc_daily_status', 'awcs_covered', 'ls_launched']);
    $scope.demographics = checkCollapse(['registered_household', 'enrolled_children', 'enrolled_women', 'lactating_enrolled_women', 'adolescent_girls', 'adhaar']);
    $scope.infrastructure = checkCollapse(['clean_water', 'functional_toilet', 'medicine_kit', 'infants_weight_scale', 'adult_weight_scale', 'infantometer', 'stadiometer']);

    $scope.goto = function (path) {
        $window.location.href = path;
    };

    $scope.goToStep = function (path, params) {
        return navigationService.getPagePath(path, params);

    };

    $scope.toggleCollapse = function (sectionId) {
        $scope.healthCollapsed = (sectionId === 'healthCollapsed') ? !$scope.healthCollapsed : true;
        $scope.icdsCasReach = (sectionId === 'icdsCasReach') ? !$scope.icdsCasReach : true;
        $scope.demographics = (sectionId === 'demographics') ? !$scope.demographics : true;
        $scope.infrastructure = (sectionId === 'infrastructure') ? !$scope.infrastructure : true;
    };

    $scope.resetCollapseParameters = function () {
        $scope.healthCollapsed = true;
        $scope.icdsCasReach = true;
        $scope.demographics = true;
        $scope.infrastructure = true;
    };

    // used by mobile only
    $scope.closeMenu = function () {
        if (isMobile) {
            document.getElementById('nav-menu').style.left = '-300px';
        }
    };

    $scope.reportAnIssue = function () {
        $scope.closeMenu();
        $uibModal.open({
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'reportIssueModal.html',
        });
    };
}

NavigationController.$inject = [
    '$window', '$rootScope', '$scope', '$route', '$routeParams', '$location', 'navigationService',
    'stateLevelAccess', 'haveAccessToAllLocations', 'haveAccessToFeatures',
    'userFullName', 'userUsername', 'isMobile', 'navMenuItems', '$uibModal', 'reportAnIssueUrl', 'isWebUser',
];

window.angular.module('icdsApp').directive('navigation', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        scope: {},
        controller: NavigationController,
        controllerAs: '$ctrl',
        templateUrl: function () {
            return templateProviderService.getTemplate('navigation.directive');
        },
    };
}]);
