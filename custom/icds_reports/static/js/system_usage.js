angular.module('icdsApp').controller('SystemUsageController', function() {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.tooltipPlacement = "right";
    vm.steps =[
        { "slug": "system_usage", "label": "System Usage"},
        { "slug": "maternal_child", "label": "Maternal & Child Health"},
        { "slug": "icds_cas_reach", "label": "ICDS-CAS Reach"},
        { "slug": "demographics", "label": "Demographics"},
        { "slug": "awc_infrastructure", "label": "AWC Infrastructure"}
    ];

    vm.step = vm.steps[0];

    this.goToStep = function(s) {
        angular.forEach(this.steps, function(value, key) {
            if (value.slug === s.slug) {
                vm.step = value;
            }
        });
    }
});