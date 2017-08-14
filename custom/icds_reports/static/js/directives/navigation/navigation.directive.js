var url = hqImport('hqwebapp/js/initial_page_data.js').reverse;

function NavigationController($window, $scope, $route, $routeParams, $location) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
    $scope.icdsCasReach = true;
    $scope.demographics = true;
    $scope.infrastructure = true;

    $scope.goto = function(path) {
        $window.location.href = path;
    };

    $scope.goToStep = function(path, params) {
        var page_path = "#/" + path;
        if (Object.keys(params).length > 0) {
            page_path += '?';
        }
        window.angular.forEach(params, function(v, k) {
            page_path += (k + '=' + v + '&');
        });
        return page_path;
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
