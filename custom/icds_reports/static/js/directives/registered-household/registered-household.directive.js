/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function RegisteredHouseholdController($scope, $routeParams, $location, $filter, demographicsService,
                                       locationsService, userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Registered Household";
    vm.steps = {
        'map': {route: '/registered_household/map', label: 'Map View'},
        'chart': {route: '/registered_household/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS CAS',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS CAS',
    };

    vm.templatePopup = function(loc, row) {
        var household = row ? $filter('indiaNumbers')(row.household) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of household registered: ',
                value: household,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = demographicsService.getRegisteredHouseholdData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse()
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ",", ' Total number of households registered'
    );
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();
    vm.chartOptions.chart.callback = function (chart) {
        var tooltip = chart.interactiveLayer.tooltip;
        tooltip.contentGenerator(function (d) {
            var findValue = function (values, date) {
                var day = _.find(values, function(num) { return num['x'] === date; });
                return d3.format(",")(day['y']);
            };
            var value = findValue(vm.chartData[0].values, d.value);
            return vm.getTooltipContent(d3.time.format('%b %Y')(new Date(d.value)), value);
        });
        return chart;
    };

    vm.getTooltipContent = function (monthName, value) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total number of household registered: ',
                value: value,
            }]
        );
    };
}

RegisteredHouseholdController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'demographicsService',
    'locationsService',
    'userLocationId',
    'storageService',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('registeredHousehold', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: RegisteredHouseholdController,
        controllerAs: '$ctrl',
    };
});
