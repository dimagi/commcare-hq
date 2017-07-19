var url = hqImport('hqwebapp/js/urllib.js').reverse;

function SystemUsageController($http, $log, $routeParams, $location, storageService) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.filters = ['gender', 'age'];
    vm.step = $routeParams.step;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();

    vm.getDataForStep = function(step) {
        var get_url = url('program_summary', step);
        $http({
            method: "GET",
            url: get_url,
            params: $location.search(),
        }).then(
            function (response) {
                vm.data = response.data.records;
            },
            function (error) {
                $log.error(error);
            }
        );
    };

    vm.steps = {
        "maternal_child": {"route": "/program_summary/maternal_child", "label": "Maternal & Child Nutrition", "data": null},
        "icds_cas_reach": {"route": "/program_summary/icds_cas_reach", "label": "ICDS CAS Reach", "data": null},
        "demographics": {"route": "/program_summary/demographics", "label": "Demographics", "data": null},
        "awc_infrastructure": {"route": "/program_summary/awc_infrastructure", "label": "AWC Infrastructure", "data": null},
    };

    vm.moveToLocation = function(loc, index) {
        if (loc === 'national') {
            $location.search('location_id', '');
            $location.search('selectedLocationLevel', -1);
            $location.search('location_name', '');
        } else {
            $location.search('location_id', loc.location_id);
            $location.search('selectedLocationLevel', index);
            $location.search('location_name', loc.name);
        }
    };

    vm.getDataForStep(vm.step);
}

SystemUsageController.$inject = ['$http', '$log', '$routeParams', '$location', 'storageService'];

window.angular.module('icdsApp').directive('systemUsage', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'system-usage.directive'),
        bindToController: true,
        controller: SystemUsageController,
        controllerAs: '$ctrl',
    };
});
