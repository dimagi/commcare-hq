

function AwcOpenedYesterdayController($routeParams, $location, storageService, systemUsageService, isAlertActive) {
    var vm = this;
    vm.data = {};
    vm.step = $routeParams.step;
    vm.filters = ['data_period'];
    vm.isAlertActive = isAlertActive;

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

    systemUsageService.getAwcOpenedData(vm.step, vm.filtersData).then(function (response) {
        vm.mapData = response.data.configs;
    });
}

AwcOpenedYesterdayController.$inject = ['$routeParams', '$location', 'storageService', 'systemUsageService',
    'isAlertActive'];

window.angular.module('icdsApp').component('awcOpenedYesterday', {
    templateUrl: function () {
        var url = hqImport('hqwebapp/js/initial_page_data').reverse;
        return url('icds-ng-template', 'awc-opened-yesterday.directive');
    },
    controller: AwcOpenedYesterdayController,
    controllerAs: '$ctrl',
});
