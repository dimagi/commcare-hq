/* global d3, _, moment */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function UnderweightChildrenReportController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService, genders, ages) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.userLocationId = userLocationId;

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

    vm.label = "Prevalence of Underweight (Weight-for-Age)";
    vm.step = $routeParams.step;
    vm.steps = {
        'map': {route: '/underweight_children/map', label: 'Map View'},
        'chart': {route: '/underweight_children/chart', label: 'Chart View'},
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
        info: 'Percentage of children between 0-5 years enrolled for Anganwadi Services with weight-for-age less than -2 standard deviations of the WHO Child Growth Standards median.',
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

    vm.chosenFilters = function() {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '0 - 5 years';
        var delimiter = gender && age ? ', ' : '';
        return gender || age ? '(' + gender + delimiter + age + ')' : '';
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.total) : 'N/A';
        var unrweighed = row ? $filter('indiaNumbers')(row.eligible - row.total) : "N/A";
        var severely_underweight = row ? d3.format(".2%")(row.severely_underweight / (row.total || 1)) : 'N/A';
        var moderately_underweight = row ? d3.format(".2%")(row.moderately_underweight / (row.total || 1)) : 'N/A';
        var normal = row ? d3.format(".2%")(row.normal / (row.total || 1)) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<div>Total Children '+ vm.chosenFilters() +' weighed in given month: <strong>' + total + '</strong></div>' +
            '<div>Number of children unweighed '+ vm.chosenFilters() +': <strong>' + unrweighed + '</strong></div>' +
            '<div>% Severely Underweight '+ vm.chosenFilters() +': <strong>' + severely_underweight + '</strong></div>' +
            '<div>% Moderately Underweight '+ vm.chosenFilters() +': <strong>' + moderately_underweight +'</strong></div>' +
            '<div>% Normal '+ vm.chosenFilters() +': <strong>' + normal + '</strong></div>';
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

        vm.myPromise = maternalChildService.getUnderweightChildrenData(vm.step, vm.filtersData).then(function(response) {
            if (vm.step === "map") {
                vm.data.mapData = response.data.report_data;
            } else if (vm.step === "chart") {
                vm.chartData = response.data.report_data.chart_data;
                vm.all_locations = response.data.report_data.all_locations;
                vm.top_five = response.data.report_data.top_five;
                vm.bottom_five = response.data.report_data.bottom_five;
                vm.location_type = response.data.report_data.location_type;
                vm.chartTicks = vm.chartData[0].values.map(function(d) { return d.x;});
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
                    parseInt(((min - range/10)/100).toFixed(2)) < 0 ?
                        0 : parseInt(((min - range/10)/100).toFixed(2)),
                    parseInt(((max + range/10)/100).toFixed(2)),
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
            },
            forceY: [0],
            callback: function(chart) {
                var tooltip = chart.interactiveLayer.tooltip;
                tooltip.contentGenerator(function (d) {

                    var findValue = function(values, date) {
                        return _.find(values, function(num) { return d3.time.format('%b %Y')(new Date(num['x'])) === date;});
                    };

                    var normal = findValue(vm.chartData[0].values, d.value).y;
                    var moderately = findValue(vm.chartData[1].values, d.value).y;
                    var severely = findValue(vm.chartData[2].values, d.value).y;
                    var unweighed = findValue(vm.chartData[0].values, d.value).unweighed;
                    var weighed = findValue(vm.chartData[0].values, d.value).all;
                    return vm.tooltipContent(d.value, normal, moderately, severely, unweighed, weighed);
                });
                return chart;
            },
        },
        caption: {
            enable: true,
            html: '<i class="fa fa-info-circle"></i> Percentage of children between ' + vm.chosenFilters() + ' enrolled for Anganwadi Services with weight-for-age less than -2 standard deviations of the WHO Child Growth Standards median.'
            + 'Children who are moderately or severely underweight have a higher risk of mortality.',
            css: {
                'text-align': 'center',
                'margin': '0 auto',
                'width': '900px',
            }
        },
    };

    vm.tooltipContent = function (monthName, normal, moderate, severe, unweighed, weighed) {

        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<div>Total Children " + vm.chosenFilters() + " weighed in given month: <strong>" + $filter('indiaNumbers')(weighed)  + "</strong></div>"
            + "<div>Number of children unweighed " + vm.chosenFilters() + ": <strong>" + $filter('indiaNumbers')(unweighed)  + "</strong></div>"
            + "<div>% children normal " + vm.chosenFilters() + ": <strong>" + d3.format(".2%")(normal) + "</strong></div>"
            + "<div>% children moderately underweight " + vm.chosenFilters() + ": <strong>" + d3.format(".2%")(moderate) + "</strong></div>"
            + "<div>% children severely underweight " + vm.chosenFilters() + ": <strong>" + d3.format(".2%")(severe) + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

UnderweightChildrenReportController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'ages'];

window.angular.module('icdsApp').directive('underweightChildrenReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: UnderweightChildrenReportController,
        controllerAs: '$ctrl',
    };
});
