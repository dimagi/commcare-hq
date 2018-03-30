/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCDailyStatusController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
                                  userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWC Daily Status";
    vm.steps = {
        'map': {route: '/awc_daily_status/map', label: 'Map View'},
        'chart': {route: '/awc_daily_status/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage AWCs',
    };
    vm.filters = ['month', 'age', 'gender'];
    vm.rightLegend = {
        info: 'Percentage of Angwanwadi Centers that were open yesterday',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var inDay = row ? $filter('indiaNumbers')(row.in_day) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_day / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of AWCs that were open yesterday: ',
                value: inDay,
            },
            {
                key: 'Total number of AWCs that have been launched: ',
                value: total,
            },
            {
                key: '% of AWCs open yesterday: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = icdsCasReachService.getAwcDailyStatusData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(false, true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%m/%d/%y', ".2%", ' Total Number of Angwanwadi Centers that were open yesterday'
    );
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
            return vm.getTooltipContent(d3.time.format('%b %Y')(new Date(d.value)), value, total);
        });
        return chart;
    };

    vm.getTooltipContent = function(monthName, value, total) {
        return "<div>Total number of AWCs that were open on <strong>" + monthName + "</strong>: <strong>" + $filter('indiaNumbers')(value) + "</strong></div>"
        + "<div>Total number of AWCs that have been launched: <strong>" + $filter('indiaNumbers')(total) + "</strong></div>"
        + "<div>% of AWCs open on <strong>" + monthName + "</strong>: <strong>" + d3.format('.2%')(value / (total || 1)) + "</strong></div>";
    };
}

AWCDailyStatusController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'icdsCasReachService',
    'locationsService',
    'userLocationId',
    'storageService',
    'baseControllersService',
];

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
