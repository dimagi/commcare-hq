/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ExclusiveBreasfeedingController($scope, $routeParams, $location, $filter, maternalChildService,
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

    vm.label = "Exclusive Breastfeeding";
    vm.steps = {
        'map': {route: '/exclusive_breastfeeding/map', label: 'Map View'},
        'chart': {route: '/exclusive_breastfeeding/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age'];
    vm.rightLegend = {
        info: '"Percentage of infants 0-6 months of age who are fed exclusively with breast milk. An infant is exclusively breastfed if they recieve only breastmilk with no additional food, liquids (even water) ensuring optimal nutrition and growth between 0 - 6 months"',
    };

    vm.templatePopup = function(loc, row) {
        var gender = genderIndex > 0 ? genders[genderIndex].name : '';
        var chosenFilters = gender ? ' (' + gender + ') ' : '';
        var children = row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var all = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of children between ages 0 - 6 months' + chosenFilters + ': ',
                value: all,
            },
            {
                key: 'Total number of children (0-6 months) exclusively breastfed in the given month' + chosenFilters + ': ',
                value: children,
            },
            {
                key: '% children (0-6 months) exclusively breastfed in the given month' + chosenFilters + ': ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getExclusiveBreastfeedingData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of infants 0-6 months of age who are fed exclusively with breast milk. \n' +
        '\n' +
        'An infant is exclusively breastfed if they recieve only breastmilk with no additional food, liquids (even water) ensuring optimal nutrition and growth between 0 - 6 months'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total number of children between ages 0 - 6 months: ',
                value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                key: 'Total number of children (0-6 months) exclusively breastfed in the given month: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: '% children (0-6 months) exclusively breastfed in the given month: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

ExclusiveBreasfeedingController.$inject = [
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

window.angular.module('icdsApp').directive('exclusiveBreastfeeding', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: ExclusiveBreasfeedingController,
        controllerAs: '$ctrl',
    };
});
