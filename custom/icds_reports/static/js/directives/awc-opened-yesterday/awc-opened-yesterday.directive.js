var url = hqImport('hqwebapp/js/initial_page_data').reverse;


function AwcOpenedYesterdayController($routeParams, $location, storageService, systemUsageService) {
    var vm = this;
    vm.data = {};
    vm.step = $routeParams.step;
    vm.filters = [];

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();

    vm.label = "AWCs Opened Yesterday";

    vm.steps = {
        'map': {route: '/awc_opened/map', label: 'MapView'},
        'chart': {route: '/awc_opened/chart', label: 'ChartView'},
    };
    vm.mapData = {};

    systemUsageService.getAwcOpenedData(vm.step, vm.filtersData).then(function(response) {
        vm.mapData = response.data.configs;
    });
}

AwcOpenedYesterdayController.$inject = ['$routeParams', '$location', 'storageService', 'systemUsageService'];

window.angular.module('icdsApp').directive('awcOpenedYesterday', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'awc-opened-yesterday.directive'),
        bindToController: true,
        controller: AwcOpenedYesterdayController,
        controllerAs: '$ctrl',
    };
});
