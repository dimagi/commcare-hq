/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function FunctionalToiletController($scope, $routeParams, $location, $filter, infrastructureService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.label = "AWCs Reported Functional Toilet";
    vm.serviceDataFunction = infrastructureService.getFunctionalToiletData;
    vm.steps = vm.getSteps('/awc_infrastructure/functional_toilet/');
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age', 'data_period'];
    vm.rightLegend = {
        info: 'Of the AWCs that submitted an Infrastructure Details form, the percentage of AWCs that reported having a functional toilet',
    };

    vm.getPopupData = function (row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return [
            {
                indicator_name: 'Number of AWCs that reported having a functional toilet: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: '% of AWCs that reported having a functional toilet: ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the AWCs that submitted an Infrastructure Details form, the percentage of AWCs that reported having a functional toilet',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Number of AWCs that reported having a functional toilet: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% of AWCs that reported having a functional toilet: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

FunctionalToiletController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'infrastructureService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('functionalToilet', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: FunctionalToiletController,
        controllerAs: '$ctrl',
    };
}]);
