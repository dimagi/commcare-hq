/* global d3, moment */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCSCoveredController($scope, $routeParams, $location, $filter, icdsCasReachService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.userLocationId = userLocationId;
    vm.filtersData = $location.search();
    vm.label = "AWCs Launched";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/awcs_covered/map', label: 'Map View'},
        'chart': {route: '/awcs_covered/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.chartData = null;
    vm.top_five = [];
    vm.bottom_five = [];
    vm.selectedLocations = [];
    vm.all_locations = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = ['age', 'gender'];
    vm.message = storageService.getKey('message') || false;

    vm.prevDay = moment().subtract(1, 'days').format('Do MMMM, YYYY');
    vm.lastDayOfPreviousMonth = moment().set('date', 1).subtract(1, 'days').format('Do MMMM, YYYY');
    vm.currentMonth = moment().format("MMMM");
    vm.showInfoMessage = function () {
        var selected_month = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selected_year = parseInt($location.search()['year']) || new Date().getFullYear();
        var current_month = new Date().getMonth() + 1;
        var current_year = new Date().getFullYear();
        return selected_month === current_month && selected_year === current_year &&
            (new Date().getDate() === 1 || new Date().getDate() === 2);
    };

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
        var awcs = row ? $filter('indiaNumbers')(row.awcs) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<p>' + vm.rightLegend.info + '</p>' +
            '<div>Number of AWCs Launched: <strong>' + awcs + '</strong></div>';
    };

    vm.loadData = function () {
        var loc_type = 'National';
        if (vm.location) {
            if (vm.location.location_type === 'supervisor') {
                loc_type = "Sector";
            } else {
                loc_type = vm.location.location_type.charAt(0).toUpperCase() + vm.location.location_type.slice(1);
            }
        }

        if (vm.location && _.contains(['block', 'supervisor', 'awc'], vm.location.location_type)) {
            vm.mode = 'sector';
            vm.steps['map'].label = loc_type + ' View';
        } else {
            vm.mode = 'map';
            vm.steps['map'].label = 'Map View: ' + loc_type;
        }

        vm.myPromise = icdsCasReachService.getAwcsCoveredData(vm.step, vm.filtersData).then(function(response) {
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
        if (!vm.userLocationId || !locationId || locationId === 'all' || locationId === 'null') {
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
                forceY: [0],
            },
            callback: function (chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === date;});
                        return d3.format(",")(day['y']);
                    };

                    var tooltipContent = vm.tooltipContent(d.value, findValue(vm.chartData[0].values, d.value));
                    return tooltipContent;
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> ' + vm.data.legendTitle,
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            },
        },
    };

    vm.tooltipContent = function(monthName, value) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + vm.data.legendTitle
            + "<div>Number of AWCs Launched: <strong>" + value + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
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
