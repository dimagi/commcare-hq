/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function AdolescentWomenController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
                                   userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Adolescent Girls (11-14 years)";
    vm.steps = {
        'map': {route: '/adolescent_girls/map', label: 'Map View'},
        'chart': {route: '/adolescent_girls/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.filters = ['age', 'gender'];
    vm.rightLegend = {
        info: 'Total number of adolescent girls who are enrolled for Anganwadi Services',
    };

    vm.templatePopup = function(loc, row) {
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Number of adolescent girls (11 - 14 years) who are enrolled for Anganwadi Services: ',
                value: valid,
            },
            {
                key: 'Total number of adolescent girls (11 - 14 years) who are registered: ',
                value: all,
            },
            {
                key: 'Percentage of registered adolescent girls (11 - 14 years) who are enrolled for Anganwadi Services: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = demographicsService.getAdolescentGirlsData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse(false)
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ",", ' Total number of adolescent girls who are enrolled for Anganwadi Services'
    );
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function (monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of adolescent girls (11 - 14 years) who are enrolled for Anganwadi Services: ',
                value: $filter('indiaNumbers')(day.y),
            },
            {
                key: 'Total number of adolescent girls (11 - 14 years) who are registered: ',
                value: $filter('indiaNumbers')(day.all),
            },
            {
                key: 'Percentage of registered adolescent girls (11 - 14 years) who are enrolled for Anganwadi Services: ',
                value: d3.format('.2%')(day.y / (day.all || 1)),
            }]
        );
    };
}

AdolescentWomenController.$inject = [
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

window.angular.module('icdsApp').directive('adolescentGirls', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: AdolescentWomenController,
        controllerAs: '$ctrl',
    };
});
