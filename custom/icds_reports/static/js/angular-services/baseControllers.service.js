/* global d3 */

window.angular.module('icdsApp').factory('baseControllersService', function() {
    return {
        BaseController: function($scope, $routeParams, $location, locationsService, userLocationId, storageService) {
            var vm = this;
            if (Object.keys($location.search()).length === 0) {
                $location.search(storageService.getKey('search'));
            } else {
                storageService.setKey('search', $location.search());
            }
            vm.userLocationId = userLocationId;
            vm.filtersData = $location.search();
            vm.step = $routeParams.step;
            vm.chartData = null;
            vm.top_five = [];
            vm.bottom_five = [];
            vm.selectedLocations = [];
            vm.all_locations = [];
            vm.location_type = null;
            vm.loaded = false;
            vm.message = storageService.getKey('message') || false;

            $scope.$watch(function() {
                return vm.selectedLocations;
            }, function (newValue, oldValue) {
                if (newValue === oldValue || !newValue || newValue.length === 0) {
                    return;
                }
                if (newValue.length === 6) {
                    var parent = newValue[3];
                    $location.search('location_id', parent.location_id);
                    $location.search('selectedLocationLevel', 3);
                    $location.search('location_name', parent.name);
                    storageService.setKey('message', true);
                    setTimeout(function() {
                        storageService.setKey('message', false);
                    }, 3000);
                }
                return newValue;
            }, true);
        },
    };
});
