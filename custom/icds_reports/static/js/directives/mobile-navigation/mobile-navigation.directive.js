var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MobileNavigationController($window, $rootScope, $scope, $route, $routeParams, $location, stateLevelAccess, haveAccessToAllLocations, haveAccessToFeatures) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.stateLevelAccess = stateLevelAccess;
    $scope.haveAccessToAllLocations = haveAccessToAllLocations;
    $scope.haveAccessToFeatures = haveAccessToFeatures;

    $scope.$on('open_nav_menu',function(event,data){
        document.getElementById('nav-menu').style.left = '0';
    });
    $scope.closeMenu = function () {
        document.getElementById('nav-menu').style.left = '-300px';
    };

    // todo
    // $scope.goto = function(path) {
    //     $window.location.href = path;
    // };
    //
    // $scope.goToStep = function(path, params) {
    //     var page_path = "#/" + path;
    //     if (Object.keys(params).length > 0) {
    //         page_path += '?';
    //     }
    //
    //     window.angular.forEach(params, function(v, k) {
    //         if (v === undefined || v === null) {
    //             v = '';
    //         }
    //         page_path += (k + '=' + v + '&');
    //     });
    //     return page_path;
    // };
}

MobileNavigationController.$inject = ['$window', '$rootScope', '$scope', '$route', '$routeParams', '$location', 'stateLevelAccess', 'haveAccessToAllLocations', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive('mobileNavigation', function() {
    return {
        restrict: 'E',
        scope: {},
        controller: MobileNavigationController,
        controllerAs: '$ctrl',
        templateUrl: url('icds-ng-template-mobile', 'mobile-navigation.directive'),
    };
});
