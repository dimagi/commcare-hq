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
                key: 'Number of AWCs that reported having a functional toilet: ',
                value: inMonth,
            },
            {
                key: '% of AWCs that reported having a functional toilet: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = infrastructureService.getFunctionalToiletData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage of AWCs that reported having a functional toilet'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of AWCs that reported having a functional toilet: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: '% of AWCs that reported having a functional toilet: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

FunctionalToiletController.$inject = [
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
