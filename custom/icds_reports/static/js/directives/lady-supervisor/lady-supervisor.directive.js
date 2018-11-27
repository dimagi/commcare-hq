/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function LadySupervisorController($scope, $http, $log, $routeParams, $location, storageService, userLocationId, haveAccessToAllLocations) {
    var vm = this;
    vm.data = {};
    vm.label = "LS Indicators";
    vm.filters = ['gender', 'age'];
    vm.userLocationId = userLocationId;
    vm.selectedLocations = [];
    vm.currentMonth = moment().format("MMMM");

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.selectedLocationLevel = storageService.getKey('search')['selectedLocationLevel'] || 0;

    vm.getData = function () {
        if (parseInt(vm.selectedLocationLevel) !== 3) {
            return;
        }
        var getUrl = url('lady_supervisor');
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
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

    vm.getDisableIndex = function () {
        var i = -1;
        if (!haveAccessToAllLocations) {
            window.angular.forEach(vm.selectedLocations, function (key, value) {
                if (key !== null && key.location_id !== 'all' && !key.user_have_access) {
                    i = value;
                }
            });
        }
        return i;
    };

    vm.moveToLocation = function (loc, index) {
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

    vm.getData();
}

LadySupervisorController.$inject = ['$scope', '$http', '$log', '$routeParams', '$location', 'storageService', 'userLocationId', 'haveAccessToAllLocations'];

window.angular.module('icdsApp').directive('ladySupervisor', function () {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'lady-supervisor.directive'),
        bindToController: true,
        controller: LadySupervisorController,
        controllerAs: '$ctrl',
    };
});
