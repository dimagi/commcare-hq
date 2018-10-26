/* global d3, _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrevalenceOfStuntingReportController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService,  genders, ages, haveAccessToAllLocations,
    baseControllersService, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations, haveAccessToFeatures);
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

    vm.label = "Prevalence of Stunting (Height-for-Age)";
    vm.steps = {
        'map': {route: '/maternal_and_child/stunting/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/stunting/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = [];

    vm.chosenFilters = function() {
        var defaultAge = '0 - 5 years';
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : defaultAge;
        var delimiter = gender && age ? ', ' : '';
        return gender || age ? '(' + gender + delimiter + age + ')' : '';
    };

    vm.rightLegend = {
        info: 'Of the children enrolled for Anganwadi services, whose height was measured, the percentage of children between ' + vm.chosenFilters() + ' who were moderately/severely stunted in the current month. \n' +
        '\n' +
        'Stunting is a sign of chronic undernutrition and has long lasting harmful consequences on the growth of a child',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.total) : 'N/A';
        var measured = row ? $filter('indiaNumbers')(row.total_measured) : 'N/A';
        var sever = row ? d3.format(".2%")(row.severe / (row.total_measured || 1)) : 'N/A';
        var moderate = row ? d3.format(".2%")(row.moderate / (row.total_measured || 1)) : 'N/A';
        var normal = row ? d3.format(".2%")(row.normal / (row.total_measured || 1)) : 'N/A';
        var unmeasured = row ? $filter('indiaNumbers')(row.total - row.total_measured) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                indicator_value: measured,
            },
            {
                indicator_name: 'Number of children ' + vm.chosenFilters() + ' unmeasured: ',
                indicator_value: unmeasured,
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + ' with severely stunted growth: ',
                indicator_value: sever,
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + ' with moderate stunted growth: ',
                indicator_value: moderate,
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + ' with normal stunted growth: ',
                indicator_value: normal,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.getPrevalenceOfStuntingData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the children enrolled for Anganwadi services, whose height was measured, the percentage of children between ' + vm.chosenFilters() + ' who were moderately/severely stunted in the current month. \n' +
        '\n' +
        'Stunting is a sign of chronic undernutrition and has long lasting harmful consequences on the growth of a child',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    vm.chartOptions.chart.callback = function(chart) {
        var tooltip = chart.interactiveLayer.tooltip;
        tooltip.contentGenerator(function (d) {

            var findValue = function (values, date) {
                return _.find(values, function(num) { return num['x'] === date; });
            };

            var normal = findValue(vm.chartData[0].values, d.value).y;
            var moderate = findValue(vm.chartData[1].values, d.value).y;
            var severe = findValue(vm.chartData[2].values, d.value).y;
            var measured = findValue(vm.chartData[0].values, d.value).measured;
            var all = findValue(vm.chartData[0].values, d.value).all;
            return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), normal, moderate, severe, measured, all);
        });
        return chart;
    };

    vm.tooltipContent = function (monthName, normal, moderate, severe, measured, all) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                indicator_value: $filter("indiaNumbers")(all),
            },
            {
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                indicator_value: $filter("indiaNumbers")(measured),
            },
            {
                indicator_name: 'Number of children ' + vm.chosenFilters() + ' unmeasured: ',
                indicator_value: $filter("indiaNumbers")(all - measured),
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + ' with severely stunted growth: ',
                indicator_value: d3.format(".2%")(severe),
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + ' with moderate stunted growth: ',
                indicator_value: d3.format(".2%")(moderate),
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + ' with normal stunted growth: ',
                indicator_value: d3.format(".2%")(normal),
            }]
        );
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
}

PrevalenceOfStuntingReportController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'ages', 'haveAccessToAllLocations', 'baseControllersService', 'haveAccessToFeatures'];

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
