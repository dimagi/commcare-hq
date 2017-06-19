var url = hqImport('hqwebapp/js/urllib.js').reverse;

function NavigationController($scope, $route, $routeParams, $location) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
}

NavigationController.$inject = ['$scope', '$route', '$routeParams', '$location'];

window.angular.module('icdsApp').directive('navigation', function() {
    return {
        restrict: 'E',
        scope: {},
        controller: NavigationController,
        templateUrl: url('icds-ng-template', 'navigation.directive'),
    };
});
