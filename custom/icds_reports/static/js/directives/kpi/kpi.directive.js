function KpiController() {
}

KpiController.$inject = [];

window.angular.module('icdsApp').directive("kpi", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
    return {
        restrict:'E',
        scope: {
            data: '=',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'kpi.directive'),
        controller: KpiController,
        controllerAs: "$ctrl",
    };
});