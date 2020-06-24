/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ProgramSummaryController($scope, $http, $log, $routeParams, $location, storageService, dateHelperService,
    navigationService, baseControllersService, userLocationId, haveAccessToAllLocations, isAlertActive, navMetadata,
                                  haveAccessToFeatures) {
    baseControllersService.BaseFilterController.call(
        this, $scope, $routeParams, $location, dateHelperService, storageService, navigationService
    );
    var vm = this;
    vm.haveAccessToFeatures = haveAccessToFeatures;
    vm.data = {};
    vm.label = "Program Summary";
    vm.haveAccessToAllLocations = haveAccessToAllLocations;
    vm.filters = ['gender', 'age', 'data_period'];
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

    vm.getDataForStep = function (step) {
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

    $scope.$watch(function () {
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
            setTimeout(function () {
                storageService.setKey('message', false);
            }, 3000);
        }
        return newValue;
    }, true);

    function _getStep(stepId) {
        return {
            "id": stepId,
            "route": "/program_summary/" + stepId,
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

    vm.showInfoMessage = function () {
        var selected_month = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selected_year =  parseInt($location.search()['year']) || new Date().getFullYear();
        var current_month = new Date().getMonth() + 1;
        var current_year = new Date().getFullYear();
        return selected_month === current_month && selected_year === current_year && new Date().getDate() === 1;
    };

    vm.setShowSystemUsageMessageCookie = function (value) {
        document.cookie = "showSystemUsageMessage=" + value + ";";
    };

    vm.getShowSystemUsageMessageCookie = function () {
        if (document.cookie.indexOf("showSystemUsageMessage=") === -1) {
            return void(0);
        }
        return document.cookie.split("showSystemUsageMessage=")[1].split(';')[0] !== 'false';
    };

    vm.closeSystemUsageMessage = function () {
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
}

ProgramSummaryController.$inject = [
    '$scope', '$http', '$log', '$routeParams', '$location', 'storageService',
    'dateHelperService', 'navigationService', 'baseControllersService', 'userLocationId',
    'haveAccessToAllLocations', 'isAlertActive', 'navMetadata', 'haveAccessToFeatures',
];

window.angular.module('icdsApp').directive("programSummary", ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        templateUrl: function () {
            return templateProviderService.getTemplate('program-summary.directive');
        },
        bindToController: true,
        controller: ProgramSummaryController,
        controllerAs: '$ctrl',
    };
}]);
