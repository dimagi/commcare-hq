/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AWCSCoveredController($scope, $routeParams, $location, $filter, icdsCasReachService, locationsService,
                               userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWCs Launched";
    vm.steps = {
        'map': {route: '/awcs_covered/map', label: 'Map View'},
        'chart': {route: '/awcs_covered/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.rightLegend = {
        info: 'Total AWCs that have launched ICDS-CAS. ' +
        'AWCs are considered launched after submitting at least one Household Registration form.',
    };
    vm.filters = ['age', 'gender'];

    vm.templatePopup = function(loc, row) {
        var awcs = row ? $filter('indiaNumbers')(row.awcs) : 'N/A';
        return '<div class="hoverinfo" style="max-width: 200px !important; white-space: normal;">' +
            '<p>' + loc.properties.name + '</p>' +
            '<p>' + vm.rightLegend.info + '</p>' +
            '<div>Number of AWCs Launched: <strong>' + awcs + '</strong></div></div>';
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = icdsCasReachService.getAwcsCoveredData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse()
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ",", ' ' + vm.data.legendTitle
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

            return vm.getTooltipContent(d3.time.format('%b %Y')(new Date(d.value)), findValue(vm.chartData[0].values, d.value));
        });
        return chart;
    };

    vm.getTooltipContent = function(monthName, value) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: vm.data.legendTitle,
                value: '',
            },
            {
                key: 'Number of AWCs Launched: ',
                value: value,
            }]
        );
    };
}

AWCSCoveredController.$inject = [
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

window.angular.module('icdsApp').directive('awcsCovered', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AWCSCoveredController,
        controllerAs: '$ctrl',
    };
});
