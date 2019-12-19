
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

window.angular.module('icdsApp', [
    'ngRoute', 'cgBusy', 'datamaps', 'nvd3',
    // these libraries aren't truly needed but do to code sharing with the web dashboard,
    // some directives depend on them to compile.
    // in the future, ideally those directives would be refactored such that the web dependencies
    // don't leak into mobile
    'ui.bootstrap',  // location directive depends on this
    'datatables', 'datatables.fixedheader', // awc reports depend on these (tabular views)
])
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
        hqImport("js/icds_dashboard_utils").addSharedRoutes($routeProvider, 'map');
    }]);
