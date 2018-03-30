/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InstitutionalDeliveriesController($scope, $routeParams, $location, $filter, maternalChildService,
                                           locationsService, userLocationId, storageService,
                                           baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Institutional deliveries";
    vm.steps = {
        'map': {route: '/institutional_deliveries/map', label: 'Map View'},
        'chart': {route: '/institutional_deliveries/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Percentage of pregnant women who delivered in a public or private medical facility in the last month. Delivery in medical instituitions is associated with a decrease in maternal mortality rate.',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var children =row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Total number of pregnant women who delivered in the last month: ',
                value: total,
            },
            {
                key: 'Total number of pregnant women who delivered in a public/private medical facilitiy in the last month: ',
                value: children,
            },
            {
                key: '% pregnant women who delivered in a public or private medical facility in the last month: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = maternalChildService.getInstitutionalDeliveriesData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(true)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ".2%",
        ' Percentage of pregnant women who delivered in a public or private medical facility in the last month. \n' +
        '\n' +
        'Delivery in medical instituitions is associated with a decrease in maternal mortality rate'
    );
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Total number of pregnant women who delivered in the last month: ',
                value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                key: 'Total number of pregnant women who delivered in a public/private medical facilitiy in the last month: ',
                value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                key: '% pregnant women who delivered in a public or private medical facility in the last month: ',
                value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

InstitutionalDeliveriesController.$inject = [
    '$scope',
    '$routeParams',
    '$location',
    '$filter',
    'maternalChildService',
    'locationsService',
    'userLocationId',
    'storageService',
    'baseControllersService',
];

window.angular.module('icdsApp').directive('institutionalDeliveries', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: InstitutionalDeliveriesController,
        controllerAs: '$ctrl',
    };
});
