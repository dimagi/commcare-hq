
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MainMobileController($scope, $route, $routeParams, $location, $window, $http,
                              isWebUser, userLocationId) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
    $scope.isWebUser = isWebUser;
    $scope.dateChanged = false;

    $scope.checkAccessToLocation = function () {
        var locationId = $location.search()['location_id'];
        if (userLocationId !== void(0) && ['', 'undefinded', 'null', void(0)].indexOf(locationId) === -1) {
            $http.get(url('have_access_to_location'), {
                params: {location_id: locationId},
            }).then(function (response) {
                if ($scope.$location.$$path !== '/access_denied' && !response.data.haveAccess) {
                    $scope.$evalAsync(function () {
                        $location.search('location_id', userLocationId);
                        $location.path('/access_denied');
                        $window.location.href = '#/access_denied';
                    });
                }
            });
        }
    };

    $scope.$on('$routeChangeStart', function () {
        $scope.checkAccessToLocation();
        var path = window.location.pathname + $location.path().substr(1);
        $window.ga('set', 'page', path);
        $window.ga('send', 'pageview', path);
    });
}

MainMobileController.$inject = [
    '$scope',
    '$route',
    '$routeParams',
    '$location',
    '$window',
    '$http',
    'isWebUser',
    'userLocationId',
];

// ui.bootstrap not truly needed - but location directive depends on it to compile
window.angular.module('icdsApp', ['ngRoute', 'cgBusy', 'ui.bootstrap'])
    .controller('MainMobileController', MainMobileController)
    .config(['$interpolateProvider', '$routeProvider', function ($interpolateProvider, $routeProvider) {
        $interpolateProvider.startSymbol('{$');
        $interpolateProvider.endSymbol('$}');
        $routeProvider
            .when("/", {
                redirectTo: '/program_summary/maternal_child',
            }).when("/program_summary/:step", {
                template: "<program-summary></program-summary>",
            });
    }]);
