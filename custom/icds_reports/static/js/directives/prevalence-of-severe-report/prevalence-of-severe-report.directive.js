/* global d3, _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrevalenceOfSevereReportController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, genders, ages, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
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
    vm.steps = {
        'map': {route: '/wasting/map', label: 'Map View'},
        'chart': {route: '/wasting/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = [];

    vm.rightLegend = {
        info: 'Percentage of children (6-60 months) enrolled for Anganwadi Services with weight-for-height below -2 standard deviations of the WHO Child Growth Standards median.',
    };

    vm.chosenFilters = function () {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : '6 - 60 months';
        var delimiter = gender && age ? ', ' : '';
        return gender || age ? '(' + gender + delimiter + age + ')' : '';
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.total_weighed) : 'N/A';
        var totalMeasured = row ? $filter('indiaNumbers')(row.total_measured) : 'N/A';
        var sever = row ? d3.format(".2%")(row.severe / (row.total_measured || 1)) : 'N/A';
        var moderate = row ? d3.format(".2%")(row.moderate / (row.total_measured || 1)) : 'N/A';
        var normal = row ? d3.format(".2%")(row.normal / (row.total_measured || 1)) : 'N/A';
        var unmeasured = row ? $filter('indiaNumbers')(row.total_height_eligible - row.total_measured) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                value: total,
            },
            {
                key: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                value: totalMeasured,
            },
            {
                key: 'Number of Children ' + vm.chosenFilters() + ' unmeasured: ',
                value: unmeasured,
            },
            {
                key: '% Severely Acute Malnutrition ' + vm.chosenFilters() + ': ',
                value: sever,
            },
            {
                key: '% Moderately Acute Malnutrition ' + vm.chosenFilters() + ': ',
                value: moderate,
            },
            {
                key: '% Normal ' + vm.chosenFilters() + ': ',
                value: normal,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getPrevalenceOfSevereData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of children between ' + vm.chosenFilters() + ' enrolled for Anganwadi Services with weight-for-height below -2 standard deviations of the WHO Child Growth Standards median. \n' +
        '\n' +
        'Wasting in children is a symptom of acute undernutrition usually as a consequence\n' +
        'of insufficient food intake or a high incidence of infectious diseases. Severe Acute Malnutrition (SAM) is nutritional status for a child who has severe wasting (weight-for-height) below -3 Z and Moderate Acute Malnutrition (MAM) is nutritional status for a child that has moderate wasting (weight-for-height) below -2Z.'
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
            var totalMeasured = findValue(vm.chartData[0].values, d.value).total_measured;
            var totalWeighed = findValue(vm.chartData[0].values, d.value).total_weighed;
            var heightEligible = findValue(vm.chartData[0].values, d.value).total_height_eligible;
            return vm.getTooltipContent(d3.time.format('%b %Y')(new Date(d.value)), normal, moderate, severe, totalWeighed, totalMeasured, heightEligible);
        });
        return chart;
    };

    vm.getTooltipContent = function (monthName, normal, moderate, severe, totalWeighed, totalMeasured, heightEligible) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                value: $filter('indiaNumbers')(totalWeighed),
            },
            {
                key: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                value: $filter('indiaNumbers')(totalMeasured),
            },
            {
                key: 'Number of Children ' + vm.chosenFilters() + ' unmeasured: ',
                value: $filter('indiaNumbers')(heightEligible - totalMeasured),
            },
            {
                key: '% children ' + vm.chosenFilters() + '  with Normal Acute Malnutrition: ',
                value: d3.format('.2%')(normal),
            },
            {
                key: '% children ' + vm.chosenFilters() + '  with Moderate Acute Malnutrition (MAM): ',
                value: d3.format('.2%')(moderate),
            },
            {
                key: '% children ' + vm.chosenFilters() + '  with Severe Acute Malnutrition (SAM): ',
                value: d3.format('.2%')(severe),
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

PrevalenceOfSevereReportController.$inject = [
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
