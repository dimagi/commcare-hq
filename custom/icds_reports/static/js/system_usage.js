var url = hqImport('hqwebapp/js/urllib.js').reverse;

angular.module('icdsApp').controller('SystemUsageController', function($http) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.tooltipPlacement = "right";

    vm.getDataForStep = function(step) {
        var get_url = url('program_summary', step.slug);
        $http({
            method: "GET",
            url: get_url,
            params: {}
        }).then(
            function (response) {
                step.data = response.data.records;
            },
            function (error) {
                console.log(error);
            });
    };

    vm.steps =[
        { "slug": "system_usage", "label": "System Usage", "data": null},
        { "slug": "maternal_child", "label": "Maternal & Child Health", "data": null},
        { "slug": "icds_cas_reach", "label": "ICDS-CAS Reach", "data": null},
        { "slug": "demographics", "label": "Demographics", "data": null},
        { "slug": "awc_infrastructure", "label": "AWC Infrastructure", "data": null}
    ];
    vm.getDataForStep(vm.steps[0]);
    vm.step = vm.steps[0];

    vm.goToStep = function(s) {
        angular.forEach(this.steps, function(value, key) {
            if (value.slug === s.slug) {
                if (!value.data) {
                    vm.getDataForStep(vm.steps[0]);
                }
                vm.step = value;
            }
        });
    }
});