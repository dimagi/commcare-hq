/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdultWeightScaleController($scope, $routeParams, $location, $filter, infrastructureService,
                                    locationsService, userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWCs Reported Weighing Scale: Mother and Child";
    vm.steps = {
        'map': {route: '/adult_weight_scale/map', label: 'Map View'},
        'chart': {route: '/adult_weight_scale/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of AWCs that reported having a weighing scale for mother and child',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of AWCs that reported having a weighing scale for mother and child: ',
                value: inMonth,
            },
            {
                key: '% of AWCs that reported having a weighing scale for mother and child: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = infrastructureService.getAdultWeightScaleData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage of AWCs that reported having a weighing scale for mother and child'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of AWCs that reported having a weighing scale for mother and child: ',
                value: $filter('indiaNumbers')(day.in_month),
            },
            {
                key: '% of AWCs that reported having a weighing scale for mother and child: ',
                value: d3.format('.2%')(day.y),
            }]
        );
    };
}

AdultWeightScaleController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'infrastructureService',
    'locationsService',
    'userLocationId',
    'storageService',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('adultWeightScale', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AdultWeightScaleController,
        controllerAs: '$ctrl',
    };
});
