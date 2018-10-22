/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdultWeightScaleController($scope, $routeParams, $location, $filter, infrastructureService,
    locationsService, userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    vm.label = "AWCs Reported Weighing Scale: Mother and Child";
    vm.steps = {
        'map': {route: '/awc_infrastructure/adult_weight_scale/map', label: 'Map View'},
        'chart': {route: '/awc_infrastructure/adult_weight_scale/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Of the AWCs that have submitted an Infrastructure Details form, the percentage of AWCs that reported having a weighing scale for mother and child',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of AWCs that reported having a weighing scale for mother and child: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: '% of AWCs that reported having a weighing scale for mother and child: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = infrastructureService.getAdultWeightScaleData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the AWCs that have submitted an Infrastructure Details form, the percentage of AWCs that reported having a weighing scale for mother and child',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Number of AWCs that reported having a weighing scale for mother and child: ',
                indicator_value: $filter('indiaNumbers')(day.in_month),
            },
            {
                indicator_name: '% of AWCs that reported having a weighing scale for mother and child: ',
                indicator_value: d3.format('.2%')(day.y),
            }]
        );
    };
}

AdultWeightScaleController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'infrastructureService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

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
