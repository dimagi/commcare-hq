/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EarlyInitiationBreastfeedingController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService, genders) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.userLocationId = userLocationId;
    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Early Initiation of Breastfeeding";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/early_initiation/map', label: 'Map View'},
        'chart': {route: '/early_initiation/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: '% Newborns',
    };
    vm.chartData = null;
    vm.top_five = [];
    vm.bottom_five = [];
    vm.selectedLocations = [];
    vm.all_locations = [];
    vm.location_type = null;
    vm.loaded = false;
    vm.filters = ['age'];

    vm.rightLegend = {
        info: 'Percentage of newborns with born with birth weight less than 2500 grams.',
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
        var total = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var birth = row ? $filter('indiaNumbers')(row.birth) : 'N/A';
        var percent = row ? d3.format('.2%')(row.birth / (row.in_month || 1)) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total Number of Children born in the given month: <strong>' + total + '</strong></div>' +
            '<div>Total Number of Children who were put to the breast within one hour of birth: <strong>' + birth + '</strong></div>' +
            '<div>% children who were put to the breast within one hour of birth: <strong>' + percent + '</strong></div>';
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

        vm.myPromise = maternalChildService.earlyInitiationBreastfeeding(vm.step, vm.filtersData).then(function(response) {
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

    vm.init = function() {
        var locationId = vm.filtersData.location_id || vm.userLocationId;
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

    vm.init();

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
                forceY: [0],
            },
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var day = _.find(vm.chartData[0].values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === d.value;});
                    return vm.tooltipContent(d.value, day);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage of children who were put to the breast within one hour of birth. \n' +
            '\n' +
            'Early initiation of breastfeeding ensure the newborn recieves the ""first milk"" rich in nutrients and encourages exclusive breastfeeding practice',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function (monthName, dataInMonth) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<p>Total Number of Children born in the given month: <strong>" + $filter('indiaNumbers')(dataInMonth.all) + "</strong></p>"
            + "<p>Total Number of Children who were put to the breast within one hour of birth: <strong>" + $filter('indiaNumbers')(dataInMonth.birth) + "</strong></p>"
            + "<p>% children who were put to the breast within one hour of birth: <strong>" + d3.format('.2%')(dataInMonth.y) + "</strong></p>";
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

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

EarlyInitiationBreastfeedingController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders'];

window.angular.module('icdsApp').directive('earlyInitiationBreastfeeding', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EarlyInitiationBreastfeedingController,
        controllerAs: '$ctrl',
    };
});
