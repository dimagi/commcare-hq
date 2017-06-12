var url = hqImport('hqwebapp/js/urllib.js').reverse;


function AwcOpenedYesterdayController($routeParams, systemUsageService) {
    var vm = this;
    vm.data = {};
    vm.step = $routeParams.step;
    vm.filters = [];

    vm.label = "AWCs Opened Yesterday";
    
    vm.steps = {
        'map': {route: '/awc_opened/map', label: 'MapView'},
        'chart': {route: '/awc_opened/chart', label: 'ChartView'},
    };
    vm.mapData = {};

    systemUsageService.getAwcOpenedData(vm.step).then(function(response) {
        vm.mapData = response.data.configs;
    });
}

AwcOpenedYesterdayController.$inject = ['$routeParams', 'systemUsageService'];

window.angular.module('icdsApp').directive('awcOpenedYesterday', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'awc-opened-yesterday.directive'),
        bindToController: true,
        controller: AwcOpenedYesterdayController,
        controllerAs: '$ctrl',
    };
});
