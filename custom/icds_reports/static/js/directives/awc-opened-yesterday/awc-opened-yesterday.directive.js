var url = hqImport('hqwebapp/js/urllib.js').reverse;


function AwcOpenedYesterdayController($routeParams, systemUsageService) {
    var vm = this;
    vm.step = $routeParams.step;
    vm.steps = [
        {route: '/awc_opened/1', label: 'MapView'},
        {route: '/awc_opened/2', label: 'ChartView'},
    ];
    vm.mapData = {};
    vm.rightLegend = {
        'average': 0,
        'info': "",
    };

    vm.fills = {
        '0%-50%': '#d60000',
        '51%-75%': '#df7400',
        '75%-100%': '#009811',
        'defaultFill': '#eef2ff',
    };

    systemUsageService.getAwcOpenedData(1).then(function(response) {
        vm.mapData = response.data.map;
        vm.rightLegend = response.data.rightLegend;
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
