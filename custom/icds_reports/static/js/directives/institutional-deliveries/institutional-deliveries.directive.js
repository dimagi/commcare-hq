/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InstitutionalDeliveriesController($scope, $routeParams, $location, $filter, maternalChildService,
    locationsService, userLocationId, storageService, haveAccessToAllLocations, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService, haveAccessToAllLocations);
    var vm = this;
    vm.label = "Institutional deliveries";
    vm.steps = {
        'map': {route: '/maternal_and_child/institutional_deliveries/map', label: 'Map View'},
        'chart': {route: '/maternal_and_child/institutional_deliveries/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Percentage Children',
    };
    vm.filters = ['gender', 'age'];
    vm.rightLegend = {
        info: 'Of the total number of women enrolled for Anganwadi services who gave birth in the last month, the percentage who delivered in a public or private medical facility.\n' +
        '\n' +
        'Delivery in medical instituitions is associated with a decrease in maternal mortality rate',
    };

    vm.templatePopup = function(loc, row) {
        var total = row ? $filter('indiaNumbers')(row.all) : 'N/A';
        var children =row ? $filter('indiaNumbers')(row.children) : 'N/A';
        var percent = row ? d3.format('.2%')(row.children / (row.all || 1)) : 'N/A';
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                indicator_name: 'Total number of pregnant women who delivered in the last month: ',
                indicator_value: total,
            },
            {
                indicator_name: 'Total number of pregnant women who delivered in a public/private medical facilitiy in the last month: ',
                indicator_value: children,
            },
            {
                indicator_name: '% pregnant women who delivered in a public or private medical facility in the last month: ',
                indicator_value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        var usePercentage = true;
        var forceYAxisFromZero = false;
        vm.myPromise = maternalChildService.getInstitutionalDeliveriesData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(usePercentage, forceYAxisFromZero)
        );
    };

    vm.init();

    var options = {
        'xAxisTickFormat': '%b %Y',
        'yAxisTickFormat': ".2%",
        'captionContent': ' Of the total number of women enrolled for Anganwadi services who gave birth in the last month, the percentage who delivered in a public or private medical facility.\n' +
        '\n' +
        'Delivery in medical instituitions is associated with a decrease in maternal mortality rate',
    };
    vm.chartOptions = vm.getChartOptions(options);
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.tooltipContent = function (monthName, dataInMonth) {
        return vm.createTooltipContent(
            monthName,
            [{
                indicator_name: 'Total number of pregnant women who delivered in the last month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.all),
            },
            {
                indicator_name: 'Total number of pregnant women who delivered in a public/private medical facilitiy in the last month: ',
                indicator_value: $filter('indiaNumbers')(dataInMonth.in_month),
            },
            {
                indicator_name: '% pregnant women who delivered in a public or private medical facility in the last month: ',
                indicator_value: d3.format('.2%')(dataInMonth.y),
            }]
        );
    };
}

InstitutionalDeliveriesController.$inject = ['$scope', '$routeParams', '$location', '$filter', 'maternalChildService', 'locationsService', 'userLocationId', 'storageService', 'haveAccessToAllLocations', 'baseControllersService'];

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
