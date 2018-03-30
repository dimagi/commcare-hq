/* global d3 */
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function EnrolledWomenController($scope, $routeParams, $location, $filter, demographicsService, locationsService,
                                 userLocationId, storageService, baseControllersService) {
    baseControllersService.BaseController.call(this, $scope, $routeParams, $location, locationsService,
        userLocationId, storageService);
    var vm = this;
    vm.label = "Pregnant Women enrolled for Anganwadi Services";
    vm.steps = {
        'map': {route: '/enrolled_women/map', label: 'Map View'},
        'chart': {route: '/enrolled_women/chart', label: 'Chart View'},
    };
    vm.data = {
        legendTitle: 'Number of Women',
    };
    vm.filters = ['gender', 'age'];

    vm.rightLegend = {
        info: 'Total number of children between the age of 0 - 6 years who are enrolled for Anganwadi Services',
    };

    vm.templatePopup = function(loc, row) {
        var valid = $filter('indiaNumbers')(row ? row.valid : 0);
        var all = $filter('indiaNumbers')(row ? row.all : 0);
        var percent = row ? d3.format('.2%')(row.valid / (row.all || 1)) : "N/A";
        return vm.createTemplatePopup(
            loc.properties.name,
            [{
                key: 'Number of pregnant women who are enrolled for Anganwadi Services: ',
                value: valid,
            },
            {
                key: 'Total number of pregnant women who are registered: ',
                value: all,
            },
            {
                key: 'Percentage of registered pregnant women who are enrolled for Anganwadi Services: ',
                value: percent,
            }]
        );
    };

    vm.loadData = function () {
        vm.setStepsMapLabel();
        vm.myPromise = demographicsService.getEnrolledWomenData(vm.step, vm.filtersData).then(
            vm.loadDataFromResponse()
        );
    };

    vm.init();

    vm.chartOptions = vm.getChartOptions(
        '%b %Y', ",", ' Total number of pregnant women who are enrolled for Anganwadi Services'
    );
    vm.chartOptions.chart.width = 1100;
    vm.chartOptions.chart.color = d3.scale.category10().range();

    vm.getTooltipContent = function(monthName, day) {
        return vm.createTooltipContent(
            monthName,
            [{
                key: 'Number of pregnant women who are enrolled for Anganwadi Services: ',
                value: $filter('indiaNumbers')(day.y),
            },
            {
                key: 'Total number of pregnant women who are registered: ',
                value: $filter('indiaNumbers')(day.all),
            },
            {
                key: 'Percentage of registered pregnant women who are enrolled for Anganwadi Services: ',
                value: d3.format('.2%')(day.y / (day.all || 1)),
            }]
        );
    };
}

EnrolledWomenController.$inject = [
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

window.angular.module('icdsApp').directive('enrolledWomen', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'map-chart'),
        bindToController: true,
        scope: {
            data: '=',
        },
        controller: EnrolledWomenController,
        controllerAs: '$ctrl',
    };
});
