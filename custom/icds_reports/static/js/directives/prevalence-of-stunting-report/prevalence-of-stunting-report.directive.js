/* global d3, _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrevalenceOfStuntingReportController($scope, $routeParams, $location, $filter, maternalChildService,
                                              locationsService, userLocationId, storageService,  genders, ages,
                                              baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
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
        'map': {route: '/stunting/map', label: 'Map View'},
        'chart': {route: '/stunting/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = [];

    vm.rightLegend = {
        info: 'Percentage of children (6-60 months) enrolled for Anganwadi Services with height-for-age below -2Z standard deviations of the WHO Child Growth Standards median.',
    };

    vm.chosenFilters = function() {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '6 - 60 months';
        var delimiter = gender && age ? ', ' : '';
        return gender || age ? '(' + gender + delimiter + age + ')' : '';
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
                key: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                value: total,
            },
            {
                key: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                value: measured,
            },
            {
                key: 'Number of children ' + vm.chosenFilters() + ' unmeasured: ',
                value: unmeasured,
            },
            {
                key: '% children ' + vm.chosenFilters() + ' with severely stunted growth: ',
                value: sever,
            },
            {
                key: '% children ' + vm.chosenFilters() + ' with moderate stunted growth: ',
                value: moderate,
            },
            {
                key: '% children ' + vm.chosenFilters() + ' with normal stunted growth: ',
                value: normal,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getPrevalenceOfStuntingData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of children ' + vm.chosenFilters() + ' enrolled for Anganwadi Services with height-for-age below -2Z standard deviations of the WHO Child Growth Standards median. \n' +
        '\n' +
        'Stunting is a sign of chronic undernutrition and has long lasting harmful consequences on the growth of a child'
    );
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
            return vm.getTooltipContent(d3.time.format('%b %Y')(new Date(d.value)), normal, moderate, severe, measured, all);
        });
        return chart;
    };

    vm.getTooltipContent = function (monthName, normal, moderate, severe, measured, all) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                value: $filter("indiaNumbers")(all),
            },
            {
                key: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                value: $filter("indiaNumbers")(measured),
            },
            {
                key: 'Number of children ' + vm.chosenFilters() + ' unmeasured: ',
                value: $filter("indiaNumbers")(all - measured),
            },
            {
                key: '% children ' + vm.chosenFilters() + ' with severely stunted growth: ',
                value: d3.format(".2%")(severe),
            },
            {
                key: '% children ' + vm.chosenFilters() + ' with moderate stunted growth: ',
                value: d3.format(".2%")(moderate),
            },
            {
                key: '% children ' + vm.chosenFilters() + ' with normal stunted growth: ',
                value: d3.format(".2%")(normal),
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

PrevalenceOfStuntingReportController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'maternalChildService',
    'locationsService',
    'userLocationId',
    'storageService',
    'genders',
    'ages',
    'baseControllersService',
];

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
