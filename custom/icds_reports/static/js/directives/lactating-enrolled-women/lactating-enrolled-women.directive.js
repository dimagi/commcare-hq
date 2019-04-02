/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function LactatingEnrolledWomenController($scope, $routeParams, $location, $filter, demographicsService,
    locationsService, userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    vm.label = "Lactating Mothers enrolled for Anganwadi Services";
    vm.steps = {
        'map': {route: '/demographics/lactating_enrolled_women/map', label: 'Map View'},
        'chart': {route: '/demographics/lactating_enrolled_women/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.filters = ['age', 'gender', 'ageServiceDeliveryDashboard'];

    vm.rightLegend = {
        info: 'Of the total number of lactating women, the percentage of lactating women enrolled for Anganwadi Services',
    };

    vm.templatePopup = function(loc, row) {
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
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
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = false;
        var forceYAxisFromZero = false;
        vm.myPromise = demographicsService.getLactatingEnrolledWomenData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ",",
        'captionContent': ' Of the total number of lactating women, the percentage of lactating women enrolled for Anganwadi Services',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = 1100;
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

    vm.tooltipContent = function(monthName, day) {
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

LactatingEnrolledWomenController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('lactatingEnrolledWomen', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: LactatingEnrolledWomenController,
        controllerAs: '$ctrl',
    };
});
