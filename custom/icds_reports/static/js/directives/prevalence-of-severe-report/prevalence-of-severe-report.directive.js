/* global d3, _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PrevalenceOfSevereReportController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService, genders, ages,
    haveAccessToAllLocations, baseControllersService, haveAccessToFeatures, isAlertActive, isMobile) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);

    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.serviceDataFunction = maternalChildService.getPrevalenceOfSevereData;

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
    vm.steps = vm.getSteps('/maternal_and_child/wasting/');
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = [];

    vm.chosenFilters = function () {
        var defaultAge = '0 - 5 years';
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var age = ageIndex > 0 ? ages[ageIndex].name : defaultAge;
        var delimiter = gender && age ? ', ' : '';
        return gender || age ? '(' + gender + delimiter + age + ')' : '';
    };

    vm.rightLegend = {
        info: 'Of the children enrolled for Anganwadi services, whose weight and height was measured, the percentage of children between ' + vm.chosenFilters() + 'who were moderately/severely wasted in the current month. \n' +
        '\n' +
        'Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition usually as a consequence of insufficient food intake or a high incidence of infectious diseases.',
    };

    vm.getPopupData = function (row) {
        var total = row ? $filter('indiaNumbers')(row.total_weighed) : 'N/A';
        var totalMeasured = row ? $filter('indiaNumbers')(row.total_measured) : 'N/A';
        var sever = row ? d3.format(".2%")(row.severe / (row.total_measured || 1)) : 'N/A';
        var moderate = row ? d3.format(".2%")(row.moderate / (row.total_measured || 1)) : 'N/A';
        var normal = row ? d3.format(".2%")(row.normal / (row.total_measured || 1)) : 'N/A';
        var unmeasured = row ? $filter('indiaNumbers')(row.total_height_eligible - row.total_measured) : 'N/A';
        return [
            {
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                indicator_value: totalMeasured,
            },
            {
                indicator_name: 'Number of Children ' + vm.chosenFilters() + ' unmeasured: ',
                indicator_value: unmeasured,
            },
            {
                indicator_name: '% Severely Acute Malnutrition ' + vm.chosenFilters() + ': ',
                indicator_value: sever,
            },
            {
                indicator_name: '% Moderately Acute Malnutrition ' + vm.chosenFilters() + ': ',
                indicator_value: moderate,
            },
            {
                indicator_name: '% Normal ' + vm.chosenFilters() + ': ',
                indicator_value: normal,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the children enrolled for Anganwadi services, whose weight and height was measured, the percentage of children between ' + vm.chosenFilters() + ' who were moderately/severely wasted in the current month. \n' +
        '\n' +
        'Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute undernutrition usually as a consequence\n' +
        'of insufficient food intake or a high incidence of infectious diseases.',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    vm.chartOptions.chart.callback = function (chart) {
        var tooltip = chart.interactiveLayer.tooltip;
        tooltip.contentGenerator(function (d) {

            var findValue = function (values, date) {
                return _.find(values, function (num) {
                    return num['x'] === date; 
                });
            };

            var normal = findValue(vm.chartData[0].values, d.value).y;
            var moderate = findValue(vm.chartData[1].values, d.value).y;
            var severe = findValue(vm.chartData[2].values, d.value).y;
            var totalMeasured = findValue(vm.chartData[0].values, d.value).total_measured;
            var totalWeighed = findValue(vm.chartData[0].values, d.value).total_weighed;
            var heightEligible = findValue(vm.chartData[0].values, d.value).total_height_eligible;
            return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), normal, moderate, severe, totalWeighed, totalMeasured, heightEligible);
        });
        return chart;
    };

    vm.tooltipContent = function (monthName, normal, moderate, severe, totalWeighed, totalMeasured, heightEligible) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' weighed in given month: ',
                indicator_value: $filter('indiaNumbers')(totalWeighed),
            },
            {
                indicator_name: 'Total Children ' + vm.chosenFilters() + ' with height measured in given month: ',
                indicator_value: $filter('indiaNumbers')(totalMeasured),
            },
            {
                indicator_name: 'Number of Children ' + vm.chosenFilters() + ' unmeasured: ',
                indicator_value: $filter('indiaNumbers')(heightEligible - totalMeasured),
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + '  with Normal Acute Malnutrition: ',
                indicator_value: d3.format('.2%')(normal),
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + '  with Moderate Acute Malnutrition (MAM): ',
                indicator_value: d3.format('.2%')(moderate),
            },
            {
                indicator_name: '% children ' + vm.chosenFilters() + '  with Severe Acute Malnutrition (SAM): ',
                indicator_value: d3.format('.2%')(severe),
            }]
        );
    };

    vm.resetAdditionalFilter = function () {
        vm.filtersData.gender = '';
        vm.filtersData.age = '';
        $location.search('gender', null);
        $location.search('age', null);
    };

    vm.resetOnlyAgeAdditionalFilter = function () {
        vm.filtersData.age = '';
        $location.search('age', null);
    };
}

PrevalenceOfSevereReportController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'maternalChildService', 'locationsService', 'dateHelperService', 'navigationService',
    'userLocationId', 'storageService', 'genders', 'ages', 'haveAccessToAllLocations',
    'baseControllersService', 'haveAccessToFeatures', 'isAlertActive', 'isMobile'];

window.angular.module('icdsApp').directive('prevalenceOfSevere', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: PrevalenceOfSevereReportController,
        controllerAs: '$ctrl',
    };
}]);
