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
        },
    };
});
