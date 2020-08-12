/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function PoshanProgressController($scope, $http, $log, $routeParams, $location, storageService, userLocationId,
                                  haveAccessToAllLocations, isAlertActive, dateHelperService) {
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
        'comparative': {route: '/poshan_progress_dashboard/comparative', label: 'Comparative Analysis'},
    };

    vm.step = $routeParams.step;

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.selectedLocationLevel = storageService.getKey('search')['selectedLocationLevel'] || 0;

    vm.getRowSpan = function (firstIndicator, secondIndicator) {
        var firstIndicatorDataLength = firstIndicator['Best performers'].length;
        var secondIndicatorDataLength = 0;
        if (secondIndicator) {
            secondIndicatorDataLength = secondIndicator['Best performers'].length;
        }
        var maxLength = Math.max(firstIndicatorDataLength, secondIndicatorDataLength);
        if (maxLength) {
            return maxLength;
        } else {
            return 1;
        }
    };

    vm.reformatAggregatedData = function (data) {
        var formattedData = [];
        var datacopy = window.angular.copy(data);
        for (var sectionHeader in datacopy) {
            var sectionData = datacopy[sectionHeader];
            var section = {};
            section['heading'] = sectionHeader;
            section['indicators'] = [];
            var indicatorsSubList = [];
            for (var key in sectionData) {
                indicatorsSubList.push(
                    {
                        'name': key,
                        'value': sectionData[key],
                    }
                );
                if (indicatorsSubList.length === 2) {
                    section['indicators'].push(indicatorsSubList);
                    indicatorsSubList = [];
                }
            }
            if (indicatorsSubList.length) {
                section['indicators'].push(indicatorsSubList);
            }
            formattedData.push(section);
        }
        return formattedData;
    };

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
                if (vm.step === 'overview' && vm.data) {
                    if (vm.data['ICDS CAS Coverage'] && vm.data['ICDS CAS Coverage']['Number of AWCs Launched'] &&
                        (vm.data['ICDS CAS Coverage']['Number of AWCs Launched'] >= 1)) {
                        vm.isLaunched = true;
                    }
                    vm.data = vm.reformatAggregatedData(vm.data);
                }
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
    'userLocationId', 'haveAccessToAllLocations', 'isAlertActive', 'dateHelperService'];

window.angular.module('icdsApp').directive('poshanProgressDashboard', function () {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'poshan-progress-dashboard.directive'),
        bindToController: true,
        controller: PoshanProgressController,
        controllerAs: '$ctrl',
    };
});
