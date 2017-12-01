/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function SystemUsageController($scope, $http, $log, $routeParams, $location, storageService, userLocationId) {
    var vm = this;
    vm.data = {};
    vm.label = "Program Summary";
    vm.filters = ['gender', 'age'];
    vm.step = $routeParams.step;
    vm.userLocationId = userLocationId;
    vm.selectedLocations = [];

    vm.prevDay = moment().subtract(1, 'days').format('Do MMMM, YYYY');
    vm.currentMonth = moment().format("MMMM");

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();

    vm.getDataForStep = function(step) {
        var get_url = url('program_summary', step);
        vm.myPromise = $http({
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

    $scope.$watch(function() {
        return vm.selectedLocations;
    }, function (newValue, oldValue) {
        if (newValue === oldValue || !newValue || newValue.length === 0) {
            return;
        }
        if (newValue.length === 6) {
            var parent = newValue[3];
            $location.search('location_id', parent.location_id);
            $location.search('selectedLocationLevel', 3);
            $location.search('location_name', parent.name);
            storageService.setKey('message', true);
            setTimeout(function() {
                storageService.setKey('message', false);
            }, 3000);
        }
        return newValue;
    }, true);

    vm.steps = {
        "maternal_child": {"route": "/program_summary/maternal_child", "label": "Maternal and Child Nutrition", "data": null},
        "icds_cas_reach": {"route": "/program_summary/icds_cas_reach", "label": "ICDS-CAS Reach", "data": null},
        "demographics": {"route": "/program_summary/demographics", "label": "Demographics", "data": null},
        "awc_infrastructure": {"route": "/program_summary/awc_infrastructure", "label": "AWC Infrastructure", "data": null},
    };

    vm.getDisableIndex = function () {
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key !== null && key.location_id === vm.userLocationId) {
                i = value;
            }
        });
        return i;
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

    vm.showInfoMessage = function () {
        var selected_month = parseInt($location.search()['month']) ||new Date().getMonth() + 1;
        var selected_year =  parseInt($location.search()['year']) || new Date().getFullYear();
        var current_month = new Date().getMonth() + 1;
        var current_year = new Date().getFullYear();
        return selected_month === current_month && selected_year === current_year && new Date().getDate() === 1;
    };

    vm.getDataForStep(vm.step);
}

SystemUsageController.$inject = ['$scope', '$http', '$log', '$routeParams', '$location', 'storageService', 'userLocationId'];

window.angular.module('icdsApp').directive('systemUsage', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'system-usage.directive'),
        bindToController: true,
        controller: SystemUsageController,
        controllerAs: '$ctrl',
    };
});
