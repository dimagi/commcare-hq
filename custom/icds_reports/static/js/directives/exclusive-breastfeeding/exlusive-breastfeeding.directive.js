/* global d3, _ */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ExclusiveBreasfeedingController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, genders, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;

    var genderIndex = _.findIndex(genders, function (x) {
        return x.id === vm.filtersData.gender;
    });
    if (genderIndex !== -1) {
        vm.genderLabel = genders[genderIndex].name;
    }

    vm.label = "Exclusive Breastfeeding";
    vm.steps = {
        'map': {route: '/maternal_and_child/exclusive_breastfeeding/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/exclusive_breastfeeding/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['age'];
    vm.rightLegend = {
        info: 'Of the total children enrolled for Anganwadi services between the ages of 0 to 6 months, the percentage that was exclusively fed with breast milk. An infant is exclusively breastfed if they receive only breastmilk with no additional food or liquids (even water), ensuring optimal nutrition and growth between 0 - 6 months\n' +
        '\n' +
        'An infant is exclusively breastfed if they receive only breastmilk with no additional food or liquids (even water), ensuring optimal nutrition and growth between 0 - 6 months',
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
                indicator_name: 'Total number of children between ages 0 - 6 months' + chosenFilters + ': ',
                indicator_value: all,
            },
            {
                indicator_name: 'Total number of children (0-6 months) exclusively breastfed in the given month' + chosenFilters + ': ',
                indicator_value: children,
            },
            {
                indicator_name: '% children (0-6 months) exclusively breastfed in the given month' + chosenFilters + ': ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.getExclusiveBreastfeedingData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total children enrolled for Anganwadi services between the ages of 0 to 6 months, the percentage that was exclusively fed with breast milk. \n' +
        '\n' +
        'An infant is exclusively breastfed if they receive only breastmilk with no additional food or liquids (even water), ensuring optimal nutrition and growth between 0 - 6 months',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of children between ages 0 - 6 months: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Total number of children (0-6 months) exclusively breastfed in the given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% children (0-6 months) exclusively breastfed in the given month: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };

    vm.resetAdditionalFilter = function() {
        vm.filtersData.gender = '';
        $location.search('gender', null);
    };
}

ExclusiveBreasfeedingController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'genders', 'haveAccessToAllLocations', 'baseControllersService'];

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
