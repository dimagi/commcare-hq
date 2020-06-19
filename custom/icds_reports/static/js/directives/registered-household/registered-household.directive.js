/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function RegisteredHouseholdController($scope, $routeParams, $location, $filter, demographicsService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.label = "Registered Household";
    vm.usePercentage = false;
    vm.serviceDataFunction = demographicsService.getRegisteredHouseholdData;
    vm.steps = vm.getSteps('/demographics/registered_household/');
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS CAS',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS CAS',
    };

    vm.getPopupData = function (row) {
        var household = row ? $filter('indiaNumbers')(row.household) : 'N/A';
        return [{
            indicator_name: 'Total number of household registered: ',
            indicator_value: household,
        }];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ",",
        'captionContent': ' Total number of households registered',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    vm.chartOptions.chart.callback = function (chart) {
        var tooltip = chart.interactiveLayer.tooltip;
        tooltip.contentGenerator(function (d) {
            var findValue = function (values, date) {
                var day = _.find(values, function (num) {
                    return num['x'] === date; 
                });
                return d3.format(",")(day['y']);
            };
            var value = findValue(vm.chartData[0].values, d.value);
            return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), value);
        });
        return chart;
    };

    vm.tooltipContent = function (monthName, value) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of household registered: ',
                indicator_value: value,
            }]
        );
    };
}

RegisteredHouseholdController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'demographicsService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('registeredHousehold', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: RegisteredHouseholdController,
        controllerAs: '$ctrl',
    };
}]);
