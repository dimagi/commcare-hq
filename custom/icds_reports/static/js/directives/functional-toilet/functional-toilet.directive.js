/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function FunctionalToiletController($scope, $routeParams, $location, $filter, infrastructureService,
    locationsService, userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWCs Reported Functional Toilet";
    vm.steps = {
        'map': {route: '/functional_toilet/map', label: 'Map View'},
        'chart': {route: '/functional_toilet/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of AWCs that reported having a functional toilet',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Number of AWCs that reported having a functional toilet: ',
                indicator_value: inMonth,
            },
            {
                indicator_name: '% of AWCs that reported having a functional toilet: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = infrastructureService.getFunctionalToiletData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Percentage of AWCs that reported having a functional toilet',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        var tooltip_content = "<p><strong>" + monthName + "</strong></p><br/>";
        tooltip_content += "<div>Number of AWCs that reported having a functional toilet: <strong>" + $filter('indiaNumbers')(dataInMonth.in_month) + "</strong></div>";
        tooltip_content += "<div>% of AWCs that reported having a functional toilet: <strong>" + d3.format('.2%')(dataInMonth.y) + "</strong></div>";

        return tooltip_content;
    };

    vm.showAllLocations = function () {
        return vm.all_locations.length < 10;
    };
}

FunctionalToiletController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'infrastructureService', 'locationsService', 'userLocationId', 'storageService', 'baseControllersService'];

window.angular.module('icdsApp').directive('functionalToilet', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: FunctionalToiletController,
        controllerAs: '$ctrl',
    };
});
