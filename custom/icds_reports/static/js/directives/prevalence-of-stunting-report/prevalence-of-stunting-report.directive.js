/* global d3*/

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrevalenceOfStuntingReportController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.label = "Prevalence of Stunting (Height-for-Age)";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/stunting/map', label: 'Map View'},
        'chart': {route: '/stunting/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.chartData = null;
    vm.top_five = [];
    vm.bottom_five = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = [];

    vm.rightLegend = {
        info: 'Percentage of children (6-60 months) enrolled for ICDS services with height-for-age below -2Z standard deviations of the WHO Child Growth Standards median.',
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
        var total = row ? $filter('indiaNumbers')(row.total) : 'N/A';
        var measured = row ? $filter('indiaNumbers')(row.total_measured) : 'N/A';
        var sever = row ? d3.format(".0%")(row.severe / (row.total || 1)) : 'N/A';
        var moderate = row ? d3.format(".0%")(row.moderate / (row.total || 1)) : 'N/A';
        var normal = row ? d3.format(".0%")(row.normal / (row.total || 1)) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total Children weighed in given month: <strong>' + total + '</strong></div>' +
            '<div>Total Children with height measured in given month: <strong>' + measured + '</strong></div>' +
            '<div>% Severely stunted: <strong>' + sever + '</strong></div>' +
            '<div>% Moderately stunted: <strong>' + moderate +'</strong></div>' +
            '<div>% Normal: <strong>' + normal + '</strong></div>';
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

        vm.myPromise = maternalChildService.getPrevalenceOfStuntingData(vm.step, vm.filtersData).then(function(response) {
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
                }) * 100);
                var min = Math.ceil(d3.min(vm.chartData, function(line) {
                    return d3.min(line.values, function(d) {
                        return d.y;
                    });
                }) * 100);
                var range = max - min;
                vm.chartOptions.chart.forceY = [((min - range/10)/100).toFixed(2), ((max + range/10)/100).toFixed(2)];
            }
        });
    };

    var init = function() {
        var locationId = vm.filtersData.location_id || userLocationId;
        if (!locationId || locationId === 'all') {
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


    vm.chartOptions = {
        chart: {
            type: 'lineChart',
            height: 450,
            width: 1100,
            margin : {
                top: 20,
                right: 60,
                bottom: 60,
                left: 80,
            },
            x: function(d){ return d.x; },
            y: function(d){ return d.y; },

            color: d3.scale.category10().range(),
            useInteractiveGuideline: true,
            clipVoronoi: false,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickFormat: function(d) {
                    return d3.time.format('%b %Y')(new Date(d));
                },
                tickValues: function() {
                    return vm.chartTicks;
                },
                axisLabelDistance: -100,
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(".2%")(d);
                },
                axisLabelDistance: 20,
            },
            forceY: [0],
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === date;});
                        return d3.format(".2%")(day['y']);
                    };

                    var tooltip_content = "<p><strong>" + d.value + "</strong></p><br/>";
                    tooltip_content += "<p>% children with normal stunted growth: <strong>" + findValue(vm.chartData[0].values, d.value) + "</strong></p>";
                    tooltip_content += "<p>% children with moderate stunted growth: <strong>" + findValue(vm.chartData[1].values, d.value) + "</strong></p>";
                    tooltip_content += "<p>% children with severely stunted growth: <strong>" + findValue(vm.chartData[2].values, d.value) + "</strong></p>";

                    return tooltip_content;
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage of children (6-60 months) enrolled for ICDS services with height-for-age below -2Z standard deviations of the WHO Child Growth Standards median. \n' +
            '\n' +
            'Stunting is a sign of chronic undernutrition and has long lasting harmful consequences on the growth of a child',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.getDisableIndex = function () {
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key !== null && key.location_id === userLocationId) {
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

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

PrevalenceOfStuntingReportController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService'];

window.angular.module('icdsApp').directive('prevalenceOfStunting', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: PrevalenceOfStuntingReportController,
        controllerAs: '$ctrl',
    };
});
