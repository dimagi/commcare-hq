/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InstitutionalDeliveriesController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, dateHelperService, navigationService, userLocationId, storageService,
    haveAccessToAllLocations, baseControllersService, isAlertActive, isMobile, haveAccessToFeatures) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        dateHelperService, navigationService, userLocationId, storageService, haveAccessToAllLocations,
        haveAccessToFeatures, isMobile);
    var vm = this;
    vm.isAlertActive = isAlertActive;
    vm.serviceDataFunction = maternalChildService.getInstitutionalDeliveriesData;

    vm.label = "Institutional deliveries";
    vm.steps = vm.getSteps('/maternal_and_child/institutional_deliveries/');
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Of the total number of women enrolled for Anganwadi services who gave birth in the given month, the percentage who delivered in a public or private medical facility.\n' +
        '\n' +
        'Delivery in medical instituitions is associated with a decrease in maternal mortality rate',
    };

    vm.getPopupData = function (row) {
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var children = row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';
        return [
            {
                indicator_name: 'Total number of pregnant women who delivered in the current month: ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total number of pregnant women who delivered in a public/private medical facilitiy in the current month: ',
                indicator_value: children,
            },
            {
                indicator_name: '% pregnant women who delivered in a public or private medical facility in the current month: ',
                indicator_value: percent,
            },
        ];
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total number of women enrolled for Anganwadi services who gave birth in the given month, the percentage who delivered in a public or private medical facility.\n' +
        '\n' +
        'Delivery in medical instituitions is associated with a decrease in maternal mortality rate',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of pregnant women who delivered in the given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Total number of pregnant women who delivered in a public/private medical facilitiy in the given month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% pregnant women who delivered in a public or private medical facility in the given month: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

InstitutionalDeliveriesController.$inject = [
    '$scope', '$routeParams', '$location', '$filter',
    'maternalChildService', 'locationsService', 'dateHelperService', 'navigationService',
    'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService', 'isAlertActive',
    'isMobile', 'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive('institutionalDeliveries', ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: templateProviderService.getMapChartTemplate,
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: InstitutionalDeliveriesController,
        controllerAs: '$ctrl',
    };
}]);
