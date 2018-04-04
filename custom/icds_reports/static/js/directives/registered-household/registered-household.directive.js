/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function RegisteredHouseholdController($scope, $routeParams, $location, $filter, demographicsService,
    locationsService, userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Registered Household";
    vm.steps = {
        'map': {route: '/registered_household/map', label: 'Map View'},
        'chart': {route: '/registered_household/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS CAS',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS CAS',
    };

    vm.templatePopup = function(loc, row) {
        var household = row ? $filter('indiaNumbers')(row.household) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of household registered: ',
                indicator_value: household,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = demographicsService.getRegisteredHouseholdData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
                vm.chartData = response.data.report_data.chart_data;
                vm.all_locations = response.data.report_data.all_locations;
                vm.top_five = response.data.report_data.top_five;
                vm.bottom_five = response.data.report_data.bottom_five;
                vm.location_type = response.data.report_data.location_type;
                vm.chartTicks = vm.chartData[0].values.map(function(d) { return d.x; });
                var max = Math.ceil(d3.max(vm.chartData, function(line) {
                    return d3.max(line.values, function(d) {
                        return d.y;
                    });
                }));
                var min = Math.ceil(d3.min(vm.chartData, function(line) {
                    return d3.min(line.values, function(d) {
                        return d.y;
                    });
                }));
                var range = max - min;
                vm.chartOptions.chart.forceY = [
                    parseInt((min - range/10).toFixed(0)) < 0 ? 0 : parseInt((min - range/10).toFixed(0)),
                    parseInt((max + range/10).toFixed(0)),
                ];
            }
        });
    };

    vm.init = function() {
        var locationId = vm.filtersData.location_id || vm.userLocationId;
        if (!locationId || ["all", "null", "undefined"].indexOf(locationId) >= 0) {
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

    vm.init();

    $scope.$on('filtersChange', function() {
        vm.loadData();
    });

    vm.getDisableIndex = function () {
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key !== null && key.location_id === vm.userLocationId) {
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

    vm.chartOptions = {
        chart: {
            type: 'lineChart',
            height: 450,
            width: 1100,
            margin: {
                top: 20,
                right: 60,
                bottom: 60,
                left: 80,
            },
            x: function (d) {
                return d.x;
            },
            y: function (d) {
                return d.y;
            },
            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            tooltips: true,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickFormat: function (d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
                tickValues: function () {
                    return vm.chartTicks;
                },
                axisLabelDistance: -100,
            },
            yAxis: {
                axisLabel: '',
                tickFormat: function (d) {
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
            },
            forceY: [0],
            callback: function (chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return num['x'] === date; });
                        return d3.format(",")(day['y']);
                    };
                    var value = findValue(vm.chartData[0].values, d.value);
                    return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), value);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Total number of households registered',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            },
        },
    };

    vm.tooltipContent = function (monthName, value) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<div>Total number of household registered: <strong>" + value + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

RegisteredHouseholdController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService', 'baseControllersService'];

window.angular.module('icdsApp').directive('registeredHousehold', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: RegisteredHouseholdController,
        controllerAs: '$ctrl',
    };
});
