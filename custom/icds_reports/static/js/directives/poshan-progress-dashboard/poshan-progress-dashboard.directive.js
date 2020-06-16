/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PoshanProgressController($scope, $http, $log, $routeParams, $location, storageService, userLocationId,
                                  haveAccessToAllLocations, isAlertActive, dateHelperService, haveAccessToFeatures) {
    var vm = this;
    vm.data = {};
    vm.label = "Poshan Progress Dashboard";
    vm.haveAccessToAllLocations = haveAccessToAllLocations;
    vm.filters = ['gender', 'age'];
    vm.userLocationId = userLocationId;
    vm.selectedLocations = [];
    vm.currentMonth = moment().format("MMMM");
    vm.isAlertActive = isAlertActive;

    vm.steps = {
        'overview': {route: '/poshan_progress_dashboard/overview', label: 'Overview'},
        'comparitive': {route: '/poshan_progress_dashboard/comparitive', label: 'Comparative Analysis'},
    };

    vm.step = $routeParams.step;

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.selectedLocationLevel = storageService.getKey('search')['selectedLocationLevel'] || 0;

    vm.getData = function () {
        vm.selectedDate = dateHelperService.getSelectedDate();
        vm.dateDisplayed = vm.selectedDate.toLocaleString('default', { month: 'short'}) + ' ' + vm.selectedDate.getFullYear();

        var step = (vm.step === 'overview') ? 'aggregated' : vm.step;
        var getUrl = url('poshan_progress_dashboard', step);
        vm.myPromise = $http({
            method: "GET",
            url: getUrl,
            params: $location.search(),
        }).then(
            function (response) {
                vm.data = response.data;
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

    vm.selectedLocation = function () {
        return storageService.getKey('selectedLocation');
    };

    vm.selectedDate = dateHelperService.getSelectedDate();

    vm.showReassignmentMessage = function () {
        var utcSelectedDate = Date.UTC(vm.selectedDate.getFullYear(), vm.selectedDate.getMonth());
        return vm.selectedLocation() && (Date.parse(vm.selectedLocation().archived_on) <= utcSelectedDate || Date.parse(vm.selectedLocation().deprecates_at) > utcSelectedDate);
    };
}

PoshanProgressController.$inject = ['$scope', '$http', '$log', '$routeParams', '$location', 'storageService',
    'userLocationId', 'haveAccessToAllLocations', 'isAlertActive', 'dateHelperService', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive('poshanProgressDashboard', function () {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'poshan-progress-dashboard.directive'),
        bindToController: true,
        controller: PoshanProgressController,
        controllerAs: '$ctrl',
    };
});
