/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCSCoveredController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
    dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
    baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.usePercentage = false;
    vm.serviceDataFunction = icdsCasReachService.getAwcsCoveredData;

    vm.label = "AWCs Launched";
    vm.steps = vm.getSteps('/icds_cas_reach/awcs_covered/');
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.filters = ['age', 'gender'];

    vm.getPopupSubheading = function () {
        return vm.rightLegend.info;
    };

    vm.getPopupData = function (row) {
        var awcs = row ? $filter('indiaNumbers')(row.awcs) : 'N/A';
        return [
            {
                indicator_name: 'Number of AWCs Launched: ',
                indicator_value: awcs,
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
                indicator_name: 'Number of AWCs Launched: ',
                indicator_value: value,
            }]
        );
    };
}

AWCSCoveredController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'icdsCasReachService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('awcsCovered', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AWCSCoveredController,
        controllerAs: '$ctrl',
    };
}]);
