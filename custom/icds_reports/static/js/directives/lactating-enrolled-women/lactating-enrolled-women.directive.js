/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function LactatingEnrolledWomenController($scope, $routeParams, $location, $filter, demographicsService,
    locationsService, userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Lactating Mothers enrolled for Anganwadi Services";
    vm.steps = {
        'map': {route: '/lactating_enrolled_women/map', label: 'Map View'},
        'chart': {route: '/lactating_enrolled_women/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.filters = ['age', 'gender'];

    vm.rightLegend = {
        info: 'Total number of lactating women who are enrolled for Anganwadi Services',
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
        'captionContent': ' Total number of lactating women who are enrolled for Anganwadi Services',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function(monthName, day) {
        return "<p><strong>" + monthName + "</strong></p><br/>"
            + "<div>Number of lactating women who are enrolled for Anganwadi Services: <strong>" + $filter('indiaNumbers')(day.y) + "</strong></div>"
            + "<div>Total number of lactating women who are registered: <strong>" +$filter('indiaNumbers')(day.all) + "</strong></div>"
            + "<div>Percentage of registered lactating women who are enrolled for Anganwadi Services: <strong>" + d3.format('.2%')(day.y / (day.all || 1)) + "</strong></div>";
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

LactatingEnrolledWomenController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'demographicsService', 'locationsService', 'userLocationId', 'storageService', 'baseControllersService'];

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
