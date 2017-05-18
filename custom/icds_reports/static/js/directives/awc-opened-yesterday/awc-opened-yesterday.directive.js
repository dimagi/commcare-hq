var url = hqImport('hqwebapp/js/urllib.js').reverse;


function AwcOpenedYesterdayController($routeParams, systemUsageService) {
    var vm = this;
    vm.step = $routeParams.step;
    vm.steps = [
        {route: '/awc_opened/1', label: 'MapView'},
        {route: '/awc_opened/2', label: 'ChartView'},
    ];
    vm.mapData = {};

    systemUsageService.getAwcOpenedData(1).then(function(response) {
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
