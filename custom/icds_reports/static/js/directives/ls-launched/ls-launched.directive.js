/* global d3 */

function LSLaunchedController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
    dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
    baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.usePercentage = false;
    vm.serviceDataFunction = icdsCasReachService.getLSLaunchedData;

    vm.label = "LSs Launched";
    vm.steps = vm.getSteps('/icds_cas_reach/ls_launched/');
    vm.data = {
        legendTitle: 'Total number of Lady supervisors who have ever submitted any form in the LS app',
    };
    vm.rightLegend = {
        info: 'Total number of Lady supervisors who have ever submitted any form in the LS app',
    };
    vm.filters = ['age', 'gender'];

    vm.getPopupSubheading = function () {
        return vm.rightLegend.info;
    };

    vm.getPopupData = function (row) {
        var lss = row ? $filter('indiaNumbers')(row.ls_launched) : 'Not Launched';
        return [
            {
                indicator_name: 'Number of LSs Launched: ',
                indicator_value: lss,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ",",
        'captionContent': ' ' + vm.data.legendTitle,
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

            return vm.tooltipContent(d3.time.format('%b %Y')(new Date(d.value)), findValue(vm.chartData[0].values, d.value));
        });
        return chart;
    };

    vm.tooltipContent = function (monthName, value) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: vm.data.legendTitle,
                indicator_value: '',
            },
            {
                indicator_name: 'Number of LSs Launched: ',
                indicator_value: value,
            }]
        );
    };
}

LSLaunchedController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'icdsCasReachService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('lsLaunched', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: LSLaunchedController,
        controllerAs: '$ctrl',
    };
}]);
