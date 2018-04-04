/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MedicineKitController($scope, $routeParams, $location, $filter, infrastructureService, locationsService,
    userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "AWCs Reported Medicine Kit";
    vm.steps = {
        'map': {route: '/medicine_kit/map', label: 'Map View'},
        'chart': {route: '/medicine_kit/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of AWCs that reported having a Medicine Kit',
    };

    vm.templatePopup = function(loc, row) {
        var inMonth = row ? $filter('indiaNumbers')(row.in_month) : 'N/A';
        var percent = row ? d3.format('.2%')(row.in_month / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of AWCs that reported having a Medicine Kit: ',
                value: inMonth,
            },
            {
                key: 'Percentage of AWCs that reported having a Medicine Kit: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = infrastructureService.getMedicineKitData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%", ' Percentage of AWCs that reported having a Medicine Kit'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of AWCs that reported having a Medicine Kit: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: 'Percentage of AWCs that reported having a Medicine Kit: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

MedicineKitController.$inject = [
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

window.angular.module('icdsApp').directive('medicineKit', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: MedicineKitController,
        controllerAs: '$ctrl',
    };
});
