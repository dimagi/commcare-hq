/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function NewbornWithLowBirthController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, dateHelperService, navigationService,
    userLocationId, storageService, genders, haveAccessToAllLocations, baseControllersService, isAlertActive,
    isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.serviceDataFunction = maternalChildService.getNewbornLowBirthData;

    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Newborns with Low Birth Weight";
    vm.steps = vm.getSteps('/maternal_and_child/low_birth/');
    vm.data = {
        legendTitle: '% Newborns',
    };
    vm.filters = ['age', 'data_period'];

    vm.rightLegend = {
        info: 'Of all the children born and weighed in the current month and enrolled for Anganwadi services, the percentage that had a birth weight less than 2500 grams. \n' +
        '\n' +
        'Newborns with Low Birth Weight are closely associated with fetal and neonatal mortality and morbidity, inhibited growth and cognitive development, and chronic diseases later in life. ',
    };

    vm.getPopupData = function (row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var lowBirth = row ? $filter('indiaNumbers')(row.low_birth) : 'N/A';
        var inMonthTotal = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.low_birth / (row.in_month || 1)) : 'N/A';
        var percentNormal = row ? d3.format('.2%')((row.in_month - row.low_birth) / (row.in_month || 1)) : 'N/A';
        var unweighedPercent = row ? d3.format('.2%')((row.all - row.in_month) / (row.all || 1)) : 'N/A';
        return [
            {
                indicator_name: chosenFilters + 'Total Number of Newborns born in given month: ',
                indicator_value: total,
            },
            {
                indicator_name: chosenFilters + 'Number of Newborns with LBW in given month: ',
                indicator_value: lowBirth,
            },
            {
                indicator_name: 'Total Number of children born and weight in given month: ',
                indicator_value: inMonthTotal,
            },
            {
                indicator_name: '% newborns with LBW in given month' + chosenFilters + ': ',
                indicator_value: percent,
            },
            {
                indicator_name: '% of children with weight in normal: ',
                indicator_value: percentNormal,
            },
            {
                indicator_name: '% Unweighted' + chosenFilters + ': ',
                indicator_value: unweighedPercent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of all the children born and weighed in the current month and enrolled for Anganwadi services, the percentage that had a birth weight less than 2500 grams. \n' +
        '\n' +
        'Newborns with Low Birth Weight are closely associated with fetal and neonatal mortality and morbidity, inhibited growth and cognitive development, and chronic diseases later in life. ',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total Number of Newborns born in given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Number of Newborns with LBW in given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.low_birth),
            },
            {
                indicator_name: 'Total Number of children born and weight in given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% newborns with LBW in given month: ',
                indicator_value: d3.format('.2%')(
                    (dataInMonth.low_birth) / (dataInMonth.in_month || 1)
                ),
            },
            {
                indicator_name: '% of children with weight in normal: ',
                indicator_value: d3.format('.2%')(
                    (dataInMonth.in_month - dataInMonth.low_birth) / (dataInMonth.in_month || 1)
                ),
            },
            {
                indicator_name: '% Unweighted: ',
                indicator_value: d3.format('.2%')(
                    (dataInMonth.all - dataInMonth.in_month) / (dataInMonth.all || 1)
                ),
            }]
        );
    };

    vm.resetAdditionalFilter = function () {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

NewbornWithLowBirthController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'maternalChildService', 'locationsService', 'dateHelperService', 'navigationService',
    'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService',
    'isAlertActive', 'isMobile', 'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('newbornLowWeight', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: NewbornWithLowBirthController,
        controllerAs: '$ctrl',
    };
}]);
