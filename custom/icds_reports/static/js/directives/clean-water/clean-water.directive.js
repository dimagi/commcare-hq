/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function CleanWaterController($scope, $routeParams, $location, $filter, infrastructureService, locationsService,
                              userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.label = "AWCs that reported having a source of clean drinking water";
    vm.steps = {
        'map': {route: '/clean_water/map', label: 'Map View'},
        'chart': {route: '/clean_water/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of AWCs that reported having a source of clean drinking water',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Number of AWCs that reported having a source of clean drinking water: ',
                value: total,
            },
            {
                key: '% of AWCs that reported having a source of clean drinking water: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = infrastructureService.getCleanWaterData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage of AWCs that reported having a source of clean drinking water'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of AWCs that reported having a source of clean drinking water: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: '% of AWCs that reported having a source of clean drinking water: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

CleanWaterController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'infrastructureService',
    'locationsService',
    'userLocationId',
    'storageService',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('cleanWater', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: CleanWaterController,
        controllerAs: '$ctrl',
    };
});
