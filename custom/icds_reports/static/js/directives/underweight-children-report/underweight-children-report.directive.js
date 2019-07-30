/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function UnderweightChildrenReportController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, genders, ages, haveAccessToAllLocations,
    baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;

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
    vm.steps = {
        'map': {route: '/maternal_and_child/underweight_children/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/underweight_children/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = [];
    vm.rightLegend = {
        info: 'Of the total children enrolled for Anganwadi services and weighed, the percentage of children between 0-5 years who were moderately/severely underweight in the current month. \n' +
        '\n' +
        'Children who are moderately or severely underweight have a higher risk of mortality. ',
    };

    vm.chosenFilters = function() {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '0 - 5 years';
        var delimiter = gender && age ? ', ' : '';
        return gender || age ? '(' + gender + delimiter + age + ')' : '';
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.weighed) : 'N/A';
        var unweighed = row ? $filter('indiaNumbers')(row.total - row.weighed) : "N/A";
        var severelyUnderweight = row ? d3.format(".2%")(row.severely_underweight / (row.weighed || 1)) : 'N/A';
        var moderatelyUnderweight = row ? d3.format(".2%")(row.moderately_underweight / (row.weighed || 1)) : 'N/A';
        var normal = row ? d3.format(".2%")(row.normal / (row.weighed || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                indicator_value: total,
            },
            {
                indicator_name: 'Number of children unweighed ' + vm.chosenFilters() + ': ',
                indicator_value: unweighed,
            },
            {
                indicator_name: '% Severely Underweight '+ vm.chosenFilters() +': ',
                indicator_value: severelyUnderweight,
            },
            {
                indicator_name: '% Moderately Underweight '+ vm.chosenFilters() +': ',
                indicator_value: moderatelyUnderweight,
            },
            {
                indicator_name: '% Normal '+ vm.chosenFilters() +': ',
                indicator_value: normal,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.getUnderweightChildrenData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

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

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total children enrolled for Anganwadi services and weighed, the percentage of children between ' + vm.chosenFilters() + ' who were moderately/severely underweight in the current month. \n' +
        '\n' +
        'Children who are moderately or severely underweight have a higher risk of mortality. ',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    vm.chartOptions.chart.callback = function(chart) {
        var tooltip = chart.interactiveLayer.tooltip;
        tooltip.contentGenerator(function (d) {

            var findValue = function(values, date) {
                return _.find(values, function(num) { return num['x'] === date; });
            };

            var normal = findValue(vm.chartData[0].values, d.value).y;
            var moderately = findValue(vm.chartData[1].values, d.value).y;
            var severely = findValue(vm.chartData[2].values, d.value).y;
            var unweighed = findValue(vm.chartData[0].values, d.value).unweighed;
            var weighed = findValue(vm.chartData[0].values, d.value).weighed;
            return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), normal, moderately, severely, unweighed, weighed);
        });
        return chart;
    };

    vm.tooltipContent = function (monthName, normal, moderate, severe, unweighed, weighed) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                indicator_value: $filter('indiaNumbers')(weighed),
            },
            {
                indicator_name: 'Number of children unweighed ' + vm.chosenFilters() + ': ',
                indicator_value: $filter('indiaNumbers')(unweighed),
            },
            {
                indicator_name: '% children normal ' + vm.chosenFilters() + ': ',
                indicator_value: d3.format(".2%")(normal),
            },
            {
                indicator_name: '% children moderately underweight ' + vm.chosenFilters() + ': ',
                indicator_value: d3.format(".2%")(moderate),
            },
            {
                indicator_name: '% children severely underweight ' + vm.chosenFilters() + ': ',
                indicator_value: d3.format(".2%")(severe),
            }]
        );
    };
}

UnderweightChildrenReportController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'ages', 'haveAccessToAllLocations', 'baseControllersService'];

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
