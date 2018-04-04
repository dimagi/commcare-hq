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

            vm.createTemplatePopup = function(header, lines) {
                var template = '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
                    '<p>' + header + '</p>';
                for (var i = 0; i < lines.length; i++) {
                    template += '<div>' + lines[i]['indicator_name'] + '<strong>' + lines[i]['indicator_value'] + '</strong></div>';
                }
                template += '</div>';
                return template;
            };
            vm.getLocationType = function() {
                if (vm.location) {
                    if (vm.location.location_type === 'supervisor') {
                        return "Sector";
                    } else {
                        return vm.location.location_type.charAt(0).toUpperCase() +
                            vm.location.location_type.slice(1);
                    }
                }
                return 'National';
            };
            vm.setStepsMapLabel = function() {
                var locType = vm.getLocationType();
                if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
                    vm.mode = 'sector';
                    vm.steps['map'].label = locType + ' View';
                } else {
                    vm.mode = 'map';
                    vm.steps['map'].label = 'Map View: ' + locType;
                }
            };
        },
    };
});
