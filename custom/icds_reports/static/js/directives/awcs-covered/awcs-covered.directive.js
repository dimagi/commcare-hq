var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCSCoveredController($scope, $routeParams, $location, $filter, icdsCasReachService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.label = "AWC Covered";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/awcs_covered/map', label: 'Map'},
    };
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS CAS',
    };
    vm.chartData = null;
    vm.top_three = [];
    vm.bottom_three = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = ['month', 'age', 'gender'];
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS CAS',
    };
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

    vm.templatePopup = function(loc, row) {
        var districts = row ? $filter('indiaNumbers')(row.districts) : 'N/A';
        var blocks = row ? $filter('indiaNumbers')(row.blocks) : 'N/A';
        var supervisors = row ? $filter('indiaNumbers')(row.supervisors) : 'N/A';
        var awcs = row ? $filter('indiaNumbers')(row.awcs) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<p>' + vm.rightLegend.info + '</p>' +
            '<div>Number of Districts Launched: <strong>' + districts + '</strong></div>' +
            '<div>Number of Blocks Launched: <strong>' + blocks + '</strong></div>' +
            '<div>Number of Sectors Launched: <strong>' + supervisors + '</strong></div>' +
            '<div>Number of AWSs Launched: <strong>' + awcs + '</strong></div>';
    };

    vm.loadData = function () {
        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
            vm.steps['map'].label = 'Sector';
        } else {
            vm.mode = 'map';
            vm.steps['map'].label = 'Map';
        }

        vm.myPromise = icdsCasReachService.getAwcsCoveredData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
                vm.chartData = response.data.report_data.chart_data;
                vm.all_locations = response.data.report_data.all_locations;
                vm.top_three = response.data.report_data.top_three;
                vm.bottom_three = response.data.report_data.bottom_three;
                vm.location_type = response.data.report_data.location_type;
                vm.chartTicks = vm.chartData[0].values.map(function(d) { return d.x; });
            }
        });
    };

    var init = function() {
        var locationId = vm.filtersData.location_id || userLocationId;
        if (!locationId || locationId === 'all' || locationId === 'null') {
            vm.loadData();
            vm.loaded = true;
            return;
        }
        locationsService.getLocation(locationId).then(function(location) {
            vm.location = location;
            vm.loadData();
            vm.loaded = true;
        });
    };

    init();

    $scope.$on('filtersChange', function() {
        vm.loadData();
    });

    vm.getDisableIndex = function () {
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key.location_id === userLocationId) {
                i = value;
            }
        });
        return i;
    };

    vm.moveToLocation = function(loc, index) {
        if (loc === 'national') {
            $location.search('location_id', '');
            $location.search('selectedLocationLevel', -1);
            $location.search('location_name', '');
        } else {
            $location.search('location_id', loc.location_id);
            $location.search('selectedLocationLevel', index);
            $location.search('location_name', loc.name);
        }
    };

    vm.showNational = function () {
        return !isNaN($location.search()['selectedLocationLevel']) && parseInt($location.search()['selectedLocationLevel']) >= 0;
    };
}

AWCSCoveredController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'icdsCasReachService', 'locationsService', 'userLocationId', 'storageService'];

window.angular.module('icdsApp').directive('awcsCovered', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AWCSCoveredController,
        controllerAs: '$ctrl',
    };
});
