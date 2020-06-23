/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function LactatingEnrolledWomenController($scope, $routeParams, $location, $filter, demographicsService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.label = "Lactating Mothers enrolled for Anganwadi Services";
    vm.serviceDataFunction = demographicsService.getLactatingEnrolledWomenData;
    vm.usePercentage = false;

    vm.steps = vm.getSteps('/demographics/lactating_enrolled_women/');
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.filters = ['age', 'gender', 'data_period'];

    vm.rightLegend = {
        info: 'Of the total number of lactating women, the percentage of lactating women enrolled for Anganwadi Services',
    };

    vm.getPopupData = function (row) {
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return [
            {
                indicator_name: 'Number of lactating women who are enrolled for Anganwadi Services: ',
                indicator_value: valid,
            },
            {
                indicator_name: 'Total number of lactating women who are registered: ',
                indicator_value: all,
            },
            {
                indicator_name: 'Percentage of registered lactating women who are enrolled for Anganwadi Services: ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ",",
        'captionContent': ' Of the total number of lactating women, the percentage of lactating women enrolled for Anganwadi Services',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = isMobile ? '' : 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getDisableIndex = function () {
        var i = -1;
        if (!haveAccessToAllLocations) {
            window.angular.forEach(vm.selectedLocations, function (key, value) {
                if (key !== null && key.location_id !== 'all' && !key.user_have_access) {
                    i = value;
                }
            });
        }
        return i;
    };

    vm.tooltipContent = function (monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Number of lactating women who are enrolled for Anganwadi Services: ',
                indicator_value: $filter('indiaNumbers')(day.y),
            },
            {
                indicator_name: 'Total number of lactating women who are registered: ',
                indicator_value: $filter('indiaNumbers')(day.all),
            },
            {
                indicator_name: 'Percentage of registered lactating women who are enrolled for Anganwadi Services: ',
                indicator_value: d3.format('.2%')(day.y / (day.all || 1)),
            }]
        );
    };
}

LactatingEnrolledWomenController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'demographicsService', 'locationsService', 'dateHelperService', 'navigationService', 'userLocationId',
    'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive', 'isMobile',
    'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('lactatingEnrolledWomen', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: LactatingEnrolledWomenController,
        controllerAs: '$ctrl',
    };
}]);
