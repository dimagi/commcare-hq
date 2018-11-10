/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCDailyStatusController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
    userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    vm.label = "AWC Daily Status";
    vm.steps = {
        'map': {route: '/icds_cas_reach/awc_daily_status/map', label: 'Map View'},
        'chart': {route: '/icds_cas_reach/awc_daily_status/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage AWCs',
    };
    vm.filters = ['month', 'age', 'gender'];
    vm.rightLegend = {
        info: 'Of the total number of AWCs, the percentage of AWCs that were open yesterday.',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var inDay = row ? $filter('indiaNumbers')(row.in_day) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_day / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of AWCs that were open yesterday: ',
                indicator_value: inDay,
            },
            {
                indicator_name: 'Total number of AWCs that have been launched: ',
                indicator_value: total,
            },
            {
                indicator_name: '% of AWCs open yesterday: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = false;
        var forceYAxisFromZero = true;
        vm.myPromise = icdsCasReachService.getAwcDailyStatusData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%m/%d/%y',
        'yAxisTickFormat': ",",
        'captionContent': ' Of the total number of AWCs, the percentage of AWCs that were open yesterday.',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();
    vm.chartOptions.chart.xAxis.rotateLabels = -45;
    vm.chartOptions.chart.callback = function(chart) {
        var tooltip = chart.interactiveLayer.tooltip;
        tooltip.contentGenerator(function (d) {
            var findValue = function (values, date) {
                var day = _.find(values, function(num) { return num.x === date; });
                return day.y;
            };
            var total = findValue(vm.chartData[0].values, d.value);
            var value = findValue(vm.chartData[1].values, d.value);
            return vm.tooltipContent(d3.time.format('%m/%d/%y')(new Date(d.value)), value, total);
        });
        return chart;
    };

    vm.tooltipContent = function(monthName, value, total) {
        return "<div>Total number of AWCs that were open on <strong>" + monthName + "</strong>: <strong>" + $filter('indiaNumbers')(value) + "</strong></div>"
        + "<div>Total number of AWCs that have been launched: <strong>" + $filter('indiaNumbers')(total) + "</strong></div>"
        + "<div>% of AWCs open on <strong>" + monthName + "</strong>: <strong>" + d3.format('.2%')(value / (total || 1)) + "</strong></div>";
    };
}

AWCDailyStatusController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'icdsCasReachService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

window.angular.module('icdsApp').directive('awcDailyStatus', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AWCDailyStatusController,
        controllerAs: '$ctrl',
    };
});
