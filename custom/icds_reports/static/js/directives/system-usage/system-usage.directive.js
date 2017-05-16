var url = hqImport('hqwebapp/js/urllib.js').reverse;

function SystemUsageController($http, $log) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.tooltipPlacement = "right";

    vm.getDataForStep = function(step) {
        var get_url = url('program_summary', step.slug);
        $http({
            method: "GET",
            url: get_url,
            params: {},
        }).then(
            function (response) {
                step.data = response.data.records;
            },
            function (error) {
                $log.error(error);
            });
    };

    vm.steps =[
        { "slug": "system_usage", "label": "System Usage", "data": null},
        { "slug": "maternal_child", "label": "Maternal & Child Health", "data": null},
        { "slug": "icds_cas_reach", "label": "ICDS-CAS Reach", "data": null},
        { "slug": "demographics", "label": "Demographics", "data": null},
        { "slug": "awc_infrastructure", "label": "AWC Infrastructure", "data": null},
    ];
    vm.getDataForStep(vm.steps[0]);
    vm.step = vm.steps[0];

    vm.goToStep = function(s) {
        window.angular.forEach(vm.steps, function(value) {
            if (value.slug === s.slug) {
                if (!value.data) {
                    vm.getDataForStep(value);
                }
                vm.step = value;
            }
        });
    };
}

SystemUsageController.$inject = ['$http', '$log'];

window.angular.module('icdsApp').directive('systemUsage', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'system-usage.directive'),
        bindToController: true,
        controller: SystemUsageController,
        controllerAs: '$ctrl',
    };
});
