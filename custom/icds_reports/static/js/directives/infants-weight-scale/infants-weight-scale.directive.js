/* global d3, moment */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfantsWeightScaleController($scope, $routeParams, $location, $filter, infrastructureService,
                                      locationsService, userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWCs Reported Weighing Scale: Infants";
    vm.steps = {
        'map': {route: '/infants_weight_scale/map', label: 'Map View'},
        'chart': {route: '/infants_weight_scale/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of AWCs that reported having a weighing scale for infants',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total of AWCs that reported having a weighing scale for infants: ',
                value: inMonth,
            },
            {
                key: 'Percentage of AWCs that reported having a weighing scale for infants: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = infrastructureService.getInfantsWeightScaleData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage of AWCs that reported having a weighing scale for infants'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of AWCs that reported having a weighing scale for infants: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: 'Percentage of AWCs that reported having a weighing scale for infants: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

InfantsWeightScaleController.$inject = [
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

window.angular.module('icdsApp').directive('infantsWeightScale', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: InfantsWeightScaleController,
        controllerAs: '$ctrl',
    };
});
