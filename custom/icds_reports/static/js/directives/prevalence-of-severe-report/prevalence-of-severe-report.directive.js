/* global d3, _, moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrevalenceOfSevereReportController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService, genders, ages) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.userLocationId = userLocationId;
    var ageIndex = _.findIndex(ages,function (x) {
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

    vm.label = "Prevalence of Wasting (Weight-for-Height)";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/wasting/map', label: 'Map View'},
        'chart': {route: '/wasting/chart', label: 'Chart View'},
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
    vm.filters = [];

    vm.rightLegend = {
        info: 'Percentage of children (6-60 months) enrolled for Anganwadi Services with weight-for-height below -2 standard deviations of the WHO Child Growth Standards median.',
    };

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
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '6 - 60 months';
        var delimiter = gender && age ? ', ' : '';
        var chosenFilters = gender || age ? '(' + gender + delimiter + age + ')' : '';
        var total = row ? $filter('indiaNumbers')(row.total) : 'N/A';
        var total_measured = row ? $filter('indiaNumbers')(row.total_measured) : 'N/A';
        var sever = row ? d3.format(".2%")(row.severe / (row.total || 1)) : 'N/A';
        var moderate = row ? d3.format(".2%")(row.moderate / (row.total || 1)) : 'N/A';
        var normal = row ? d3.format(".2%")(row.normal / (row.total || 1)) : 'N/A';
        var unmeasured = row ? d3.format(".2%")((row.total - (row.normal + row.severe + row.moderate)) / (row.total || 1)) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total Children ' + chosenFilters + ' weighed in given month: <strong>' + total + '</strong></div>' +
            '<div>Total Children ' + chosenFilters + ' with height measured in given month: <strong>' + total_measured + '</strong></div>' +
            '<div>% Unmeasured ' + chosenFilters + ': <strong>' + unmeasured + '</strong></div>' +
            '<div>% Severely Acute Malnutrition ' + chosenFilters + ': <strong>' + sever + '</strong></div>' +
            '<div>% Moderately Acute Malnutrition ' + chosenFilters + ': <strong>' + moderate +'</strong></div>' +
            '<div>% Normal ' + chosenFilters + ': <strong>' + normal + '</strong></div></ul>';
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

        vm.myPromise = maternalChildService.getPrevalenceOfSevereData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
                vm.chartData = response.data.report_data.chart_data;
                vm.top_five = response.data.report_data.top_five;
                vm.bottom_five = response.data.report_data.bottom_five;
                vm.all_locations = response.data.report_data.all_locations;
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
        if (!vm.userLocationId || !locationId || locationId === 'all') {
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
            },
            forceY: [0],
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function (values, date) {
                        var day = _.find(values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === date;});
                        return day['y'];
                    };

                    var normal = findValue(vm.chartData[0].values, d.value);
                    var moderate = findValue(vm.chartData[1].values, d.value);
                    var severe = findValue(vm.chartData[2].values, d.value);
                    return vm.tooltipContent(d.value, normal, moderate, severe);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage of children between 6 - 60 months enrolled for Anganwadi Services with weight-for-height below -2 standard deviations of the WHO Child Growth Standards median. \n' +
            '\n' +
            'Wasting in children is a symptom of acute undernutrition usually as a consequence\n' +
            'of insufficient food intake or a high incidence of infectious diseases. Severe Acute Malnutrition (SAM) is nutritional status for a child who has severe wasting (weight-for-height) below -3 Z and Moderate Acute Malnutrition (MAM) is nutritional status for a child that has moderate wasting (weight-for-height) below -2Z.',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function (monthName, normal, moderate, severe) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<p>% children with Normal Acute Malnutrition: <strong>" + d3.format(".2%")(normal) + "</strong></p>"
            + "<p>% children with Moderate Acute Malnutrition (MAM): <strong>" + d3.format(".2%")(moderate) + "</strong></p>"
            + "<p>% children with Severe Acute Malnutrition (SAM): <strong>" + d3.format(".2%")(severe) + "</strong></p>"
            + "<p>% Unmeasured: <strong>" + d3.format(".2%")((1 - (normal + moderate + severe))) + "</strong></p>";
    };

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

PrevalenceOfSevereReportController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'ages'];

window.angular.module('icdsApp').directive('prevalenceOfSevere', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: PrevalenceOfSevereReportController,
        controllerAs: '$ctrl',
    };
});
