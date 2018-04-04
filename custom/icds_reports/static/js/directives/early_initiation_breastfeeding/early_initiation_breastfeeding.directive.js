/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EarlyInitiationBreastfeedingController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, genders, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Early Initiation of Breastfeeding";
    vm.steps = {
        'map': {route: '/early_initiation/map', label: 'Map View'},
        'chart': {route: '/early_initiation/chart', label: 'Chart View'},
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
        var total = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var birth = row ? $filter('indiaNumbers')(row.birth) : 'N/A';
        var percent = row ? d3.format('.2%')(row.birth / (row.in_month || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total Number of Children born in the given month' + chosenFilters + ': ',
                value: total,
            },
            {
                key: 'Total Number of Children who were put to the breast within one hour of birth' + chosenFilters + ': ',
                value: birth,
            },
            {
                key: '% children who were put to the breast within one hour of birth' + chosenFilters + ': ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.earlyInitiationBreastfeeding(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of children who were put to the breast within one hour of birth. \n' +
        '\n' +
        'Early initiation of breastfeeding ensure the newborn recieves the ""first milk"" rich in nutrients and encourages exclusive breastfeeding practice'
    );
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total Number of Children born in the given month: ',
                value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                key: 'Total Number of Children who were put to the breast within one hour of birth: ',
                value: $filter('indiaNumbers')(dataInMonth.birth),
            },
            {
                key: '% children who were put to the breast within one hour of birth: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

EarlyInitiationBreastfeedingController.$inject = [
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

window.angular.module('icdsApp').directive('earlyInitiationBreastfeeding', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EarlyInitiationBreastfeedingController,
        controllerAs: '$ctrl',
    };
});
