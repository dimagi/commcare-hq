var url = hqImport('hqwebapp/js/urllib.js').reverse;

function NavigationController($window, $scope, $route, $routeParams, $location) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;

    $scope.goto = function(path) {
        $window.location.href = path;
    };
}

NavigationController.$inject = ['$window', '$scope', '$route', '$routeParams', '$location'];

window.angular.module('icdsApp').directive('navigation', function() {
    return {
        restrict: 'E',
        scope: {},
        controller: NavigationController,
        controllerAs: '$ctrl',
        templateUrl: url('icds-ng-template', 'navigation.directive'),
    };
});
