/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ImmunizationCoverageController($scope, $routeParams, $location, $filter, maternalChildService,
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

    vm.label = "Immunization coverage (at age 1 year)";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/immunization_coverage/map', label: 'Map View'},
        'chart': {route: '/immunization_coverage/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
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
        info: 'Percentage of children 1 year+ who have received complete immunization as per National Immunization Schedule of India required by age 1.<br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/>If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1',
    };
    vm.message = storageService.getKey('message') || false;

    vm.prevDay = moment().subtract(1, 'days').format('Do MMMM, YYYY');
    vm.currentMonth = moment().format("MMMM");
    vm.showInfoMessage = function () {
        var selected_month = parseInt($location.search()['month']) ||new Date().getMonth() + 1;
        var selected_year =  parseInt($location.search()['year']) || new Date().getFullYear();
        var current_month = new Date().getMonth() + 1;
        var current_year = new Date().getFullYear();
        return selected_month === current_month && selected_year === current_year && new Date().getDate() === 1;
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
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var children = row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total number of ICDS Child beneficiaries older than 1 year' + chosenFilters + ': <strong>' + total + '</strong></div>' +
            '<div>Total number of children who have recieved complete immunizations required by age 1' + chosenFilters + ': <strong>' + children + '</strong></div>' +
            '<div>% of children who have recieved complete immunizations required by age 1' + chosenFilters + ': <strong>' + percent + '</strong></div>';
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


        vm.myPromise = maternalChildService.getImmunizationCoverageData(vm.step, vm.filtersData).then(function(response) {
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
                vm.chartOptions.chart.forceY = [
                    ((min - range/10)/100).toFixed(2) < 0 ? 0 : ((min - range/10)/100).toFixed(2),
                    ((max + range/10)/100).toFixed(2),
                ];
            }
        });
    };

    vm.init = function() {
        var locationId = vm.filtersData.location_id || vm.userLocationId;
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

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };

    vm.chartOptions = {
        chart: {
            type: 'lineChart',
            height: 450,
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
            tooltips: true,
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
                    var dataInMonth = _.find(vm.chartData[0].values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === d.value;});
                    return vm.tooltipContent(d.value, dataInMonth);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage of children 1 year+ who have received complete immunization as per National Immunization Schedule of India required by age 1. <br/><br/>This includes the following immunizations:<br/>If Pentavalent path: Penta1/2/3, OPV1/2/3, BCG, Measles, VitA1<br/> If DPT/HepB path: DPT1/2/3, HepB1/2/3, OPV1/2/3, BCG, Measles, VitA1',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function (monthName, dataInMonth) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<p>Total number of ICDS Child beneficiaries older than 1 year: <strong>" + $filter('indiaNumbers')(dataInMonth.all) + "</strong></p>"
            + "<p>Total number of children who have recieved complete immunizations required by age 1: <strong>" + $filter('indiaNumbers')(dataInMonth.in_month) + "</strong></p>"
            + "<p>% of children who have recieved complete immunizations required by age 1: <strong>" + d3.format('.2%')(dataInMonth.y) + "</strong></p>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

ImmunizationCoverageController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders'];

window.angular.module('icdsApp').directive('immunizationCoverage', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: ImmunizationCoverageController,
        controllerAs: '$ctrl',
    };
});
