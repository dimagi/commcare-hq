/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function DemographicsController($scope, $http, $log, $routeParams, $location, storageService, dateHelperService,
    userLocationId, haveAccessToAllLocations, isAlertActive, navMetadata) {
    var vm = this;
    vm.data = {};
    vm.label = "Demographics";
    vm.filters = ['gender', 'age'];
    vm.step = $routeParams.step;
    vm.userLocationId = userLocationId;
    vm.selectedLocations = [];
    vm.isAlertActive = isAlertActive;

    vm.prevDay = moment().subtract(1, 'days').format('Do MMMM, YYYY');
    vm.lastDayOfPreviousMonth = moment().set('date', 1).subtract(1, 'days').format('Do MMMM, YYYY');

    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }

    vm.filtersData = $location.search();

    vm.getDataForStep = function(step) {
        var get_url = 'http://localhost:8000/a/icds-cas/demographics/registered_household/map/';
        //var get_url = url('demographics');
        vm.myPromise = $http({
            method: "GET",
            url: get_url,
            params: $location.search(),
        }).then(
            function(response) {
                vm.data = response.data;
                console.log("*****************");
                console.table(vm.data);
            },
            function(error) {
                $log.error(error);
            }
        );
    };

    $scope.$watch(function() {
        return vm.selectedLocations;
    }, function(newValue, oldValue) {
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

    function _getStep(stepId) {
        return {
            "id": stepId,
            "route": "/demographics/" + stepId,
            "label": navMetadata[stepId]["label"],
            "image": navMetadata[stepId]["image"],
        };
    }
    vm.steps = {
        "maternal_child": _getStep("maternal_child"),
        "icds_cas_reach": _getStep("icds_cas_reach"),
        "demographics": _getStep("demographics"),
        "awc_infrastructure": _getStep("awc_infrastructure"),
    };
    vm.getDisableIndex = function() {
        var i = -1;
        if (!haveAccessToAllLocations) {
            window.angular.forEach(vm.selectedLocations, function(key, value) {
                if (key !== null && key.location_id !== 'all' && !key.user_have_access) {
                    i = value;
                }
            });
        }
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

    vm.showInfoMessage = function() {
        var selected_month = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selected_year = parseInt($location.search()['year']) || new Date().getFullYear();
        var current_month = new Date().getMonth() + 1;
        var current_year = new Date().getFullYear();
        return selected_month === current_month && selected_year === current_year && new Date().getDate() === 1;
    };

    vm.setShowSystemUsageMessageCookie = function(value) {
        document.cookie = "showSystemUsageMessage=" + value + ";";
    };

    vm.getShowSystemUsageMessageCookie = function() {
        if (document.cookie.indexOf("showSystemUsageMessage=") === -1) {
            return void(0);
        }
        return document.cookie.split("showSystemUsageMessage=")[1].split(';')[0] !== 'false';
    };

    vm.closeSystemUsageMessage = function() {
        vm.setShowSystemUsageMessageCookie("false");
        vm.showSystemUsageMessage = false;
    };

    if (vm.getShowSystemUsageMessageCookie() !== false) {
        vm.showSystemUsageMessage = true;
        vm.setShowSystemUsageMessageCookie("true");
    } else if (vm.getShowSystemUsageMessageCookie() === void(0)) {
        vm.showSystemUsageMessage = true;
        vm.setShowSystemUsageMessageCookie("true");
    } else {
        vm.showSystemUsageMessage = false;
    }

    vm.getDataForStep(vm.step);
    vm.currentStepMeta = vm.steps[vm.step];

    // mobile only, update if filters are visible over the program summary
    vm.filtersOpen = false;
    $scope.$on('openFilterMenu', function() {
        vm.filtersOpen = true;
    });
    $scope.$on('closeFilterMenu', function() {
        vm.filtersOpen = false;
    });
    $scope.$on('mobile_filter_data_changed', function(event, data) {
        vm.filtersOpen = false;
        if (!data.location) {
            vm.moveToLocation('national', -1);
        } else {
            vm.moveToLocation(data.location, data.locationLevel);
        }
        dateHelperService.updateSelectedMonth(data['month'], data['year']);
        storageService.setKey('search', $location.search());
        $scope.$emit('filtersChange');
    });
    vm.selectedMonthDisplay = dateHelperService.getSelectedMonthDisplay();
}

DemographicsController.$inject = ['$scope', '$http', '$log', '$routeParams', '$location', 'storageService',
    'dateHelperService', 'userLocationId', 'haveAccessToAllLocations', 'isAlertActive', 'navMetadata'
];

window.angular.module('icdsApp').directive("demographics", ['templateProviderService', function(templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: function() {
            return templateProviderService.getTemplate('demographics.directive');
        },
        bindToController: true,
        controller: DemographicsController,
        controllerAs: '$ctrl',
    };
}]);