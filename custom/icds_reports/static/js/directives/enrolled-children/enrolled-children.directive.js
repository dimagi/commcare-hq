/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EnrolledChildrenController($scope, $routeParams, $location, $filter, demographicsService,
                                             locationsService, userLocationId, storageService, genders, ages) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.userLocationId = userLocationId;
    vm.filtersData = $location.search();

    var ageIndex = _.findIndex(ages, function (x) {
        return x.id === vm.filtersData.age;
    });
    if (ageIndex !== -1) {
        vm.ageLabel = ages[ageIndex].name;
    }

    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Children (0-6 years) who are enrolled for ICDS services";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/enrolled_children/map', label: 'Map View'},
        'chart': {route: '/enrolled_children/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Children',
    };
    vm.chartData = null;
    vm.top_five = [];
    vm.bottom_five = [];
    vm.selectedLocations = [];
    vm.all_locations = [];
    vm.location_type = null;
    vm.loaded = false;
    if (vm.step === 'chart') {
        vm.filters = ['age'];
    } else {
        vm.filters = [];
    }

    vm.rightLegend = {
        info: 'Total number of children between the age of 0 - 6 years who are enrolled for ICDS services',
    };

    vm.message = storageService.getKey('message') || false;

    vm.hideRanking = true;

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
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        return '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total number of children between the age of 0 - 6 years who are enrolled for ICDS services: <strong>' + valid + '</strong></div>';
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

        vm.myPromise = demographicsService.getEnrolledChildrenData(vm.step, vm.filtersData).then(function(response) {
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
                vm.chartOptions.chart.forceY = [0, (max + range/10).toFixed(2)];
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
            type: 'multiBarChart',
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
            useInteractiveGuideline: false,
            tooltip: function (key, x) {
                var data = _.find(vm.chartData[0].values, function(num) { return num.x === x;});
                return vm.tooltipContent(data, x);
            },
            clipVoronoi: false,
            xAxis: {
                axisLabel: '',
                showMaxMin: true,
                tickValues: function() {
                    return ["0-1 month", "1-6 months", "6-12 months", "1-3 years", "3-6 years"];
                },
            },

            yAxis: {
                axisLabel: '',
                tickFormat: function(d){
                    return d3.format(",")(d);
                },
                axisLabelDistance: 20,
                forceY: [0],
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Total number of children between the age of 0 - 6 years who are enrolled for ICDS services',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function (dataInMonth, x) {
        var average = (dataInMonth.all !== 0) ? d3.format(".2%")(dataInMonth.y / dataInMonth.all) : 0;
        return "<p>Total number of children between the age of 0 - 6 years who are enrolled for ICDS services: <strong>"
            + $filter('indiaNumbers')(dataInMonth.all) + "</strong></p>"
            + "<p>% of children " + x + ": <strong>" + average + "</strong></p>";
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
        vm.filtersData.age = '';
        $location.search('gender', null);
        $location.search('age', null);
    };

    vm.resetOnlyAgeAdditionalFilter = function() {
        vm.filtersData.age = '';
        $location.search('age', null);
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

EnrolledChildrenController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'ages'];

window.angular.module('icdsApp').directive('enrolledChildren', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EnrolledChildrenController,
        controllerAs: '$ctrl',
    };
});
