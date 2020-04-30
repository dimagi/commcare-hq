/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfantsWeightScaleController($scope, $routeParams, $location, $filter, infrastructureService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.label = "AWCs Reported Weighing Scale: Infants";
    vm.serviceDataFunction = infrastructureService.getInfantsWeightScaleData;
    vm.steps = vm.getSteps('/awc_infrastructure/infants_weight_scale/');
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Of the AWCs that have submitted an Infrastructure Details form, the percentage of AWCs that reported having a weighing scale for infants',
    };

    vm.getPopupData = function (row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return [
            {
                indicator_name: 'Total of AWCs that reported having a weighing scale for infants: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: 'Percentage of AWCs that reported having a weighing scale for infants: ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the AWCs that have submitted an Infrastructure Details form, the percentage of AWCs that reported having a weighing scale for infants',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Number of AWCs that reported having a weighing scale for infants: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: 'Percentage of AWCs that reported having a weighing scale for infants: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

InfantsWeightScaleController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'infrastructureService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('infantsWeightScale', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: InfantsWeightScaleController,
        controllerAs: '$ctrl',
    };
}]);
