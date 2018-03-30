/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function NewbornWithLowBirthController($scope, $routeParams, $location, $filter, maternalChildService,
                                             locationsService, userLocationId, storageService, genders,
                                       baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Newborns with Low Birth Weight";
    vm.steps = {
        'map': {route: '/low_birth/map', label: 'Map View'},
        'chart': {route: '/low_birth/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: '% Newborns',
    };
    vm.filters = ['age'];

    vm.rightLegend = {
        info: 'Percentage of newborns with born with birth weight less than 2500 grams.',
    };

    vm.templatePopup = function(loc, row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var lowBirth = row ? $filter('indiaNumbers')(row.low_birth) : 'N/A';
        var percent = row ? d3.format('.2%')(row.low_birth / (row.in_month || 1)) : 'N/A';
        var unweighedPercent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: chosenFilters + 'Total Number of Newborns born in given month: ',
                value: total,
            },
            {
                key: chosenFilters + 'Number of Newborns with LBW in given month: ',
                value: lowBirth,
            },
            {
                key: '% newborns with LBW in given month' + chosenFilters + ': ',
                value: percent,
            },
            {
                key: '% Unweighted' + chosenFilters + ': ',
                value: unweighedPercent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getNewbornLowBirthData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of newborns with born with birth weight less than 2500 grams. \n' +
        '\n' +
        'Newborns with Low Birth Weight are closely associated with foetal and neonatal mortality and morbidity, inhibited growth and cognitive development, and chronic diseases later in life'
    );
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total Number of Newborns born in given month: ',
                value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                key: 'Number of Newborns with LBW in given month: ',
                value: $filter('indiaNumbers')(dataInMonth.low_birth),
            },
            {
                key: '% newborns with LBW in given month: ',
                value: d3.format('.2%')(dataInMonth.y),
            },
            {
                key: '% Unweighted: ',
                value: d3.format('.2%')(dataInMonth.in_month / (dataInMonth.all || 1)),
            }]
        );
    };

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

NewbornWithLowBirthController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'maternalChildService',
    'locationsService',
    'userLocationId',
    'storageService',
    'genders',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('newbornLowWeight', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: NewbornWithLowBirthController,
        controllerAs: '$ctrl',
    };
});
