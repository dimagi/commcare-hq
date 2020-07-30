/* global moment */

function CasExportController($window, $location, locationHierarchy, locationsService, downloadService, userLocationId, isAlertActive) {
    var vm = this;
    vm.isAlertActive = isAlertActive;

    vm.months = [];
    vm.monthsCopy = [];
    vm.years = [];
    vm.yearsCopy = [];

    vm.selectedLocations = []
    vm.userLocationId = userLocationId;
    vm.selectedLocationId = vm.userLocationId;
    vm.selectedIndicator = null;

    var locationsCache = {};
    var ALL_OPTION = locationsService.ALL_OPTION;

    locationsService.getRootLocations().then(function (data) {
        vm.locations = data.locations;
    });
    var now = moment();
    if (now.date() <= 6) {
        now.subtract(2, 'months');
    } else {
        now.subtract(1, 'months');
    }

    vm.selectedMonth = now.month() + 1;
    vm.selectedYear = now.year();

    vm.updateSelectedDate = function () {
        vm.selectedDate = vm.selectedMonth ? new Date(vm.selectedYear, vm.selectedMonth - 1) : new Date();
    };

    vm.updateSelectedDate();

    window.angular.forEach(moment.months(), function (key, value) {
        vm.monthsCopy.push({
            name: key,
            id: value + 1,
        });
    });

    if (vm.selectedYear === new Date().getFullYear()) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id < new Date().getMonth() || (month.id === new Date().getMonth() && moment().date() > 6);
        });
    } else if (vm.selectedYear === 2017) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id >= 3;
        });
    } else {
        vm.months = vm.monthsCopy;
    }

    for (var year = 2017; year <= new Date().getFullYear(); year++) {
        vm.yearsCopy.push({
            name: year,
            id: year,
        });
    }
    vm.years = vm.yearsCopy;

    var initHierarchy = function() {
        hierarchyData = locationsService.initHierarchy(locationHierarchy);
        vm.hierarchy = hierarchyData['hierarchy'];
        vm.maxLevels = hierarchyData['levels'];
    };

    initHierarchy();
    locationsCache = locationsService.initLocations(vm, locationsCache);

    vm.indicators = [
        {id: 'child_health_monthly', name: 'Child'},
        {id: 'ccs_record_monthly', name: 'Pregnant and Lactating Women'},
        {id: 'agg_awc', name: 'AWC'},
    ];

    vm.allFiltersSelected = function () {
        return vm.selectedLocationId !== null && vm.selectedMonth !== null && vm.selectedYear !== null && vm.selectedIndicator !== null;
    };

    vm.onSelectMonth = function () {
        vm.updateSelectedDate();
    };

    vm.onSelectYear = function (year) {
        var latest = new Date();
        var offset = latest.getDate() < 15 ? 2 : 1;
        latest.setMonth(latest.getMonth() - offset);
        if (year.id > latest.getFullYear()) {
            vm.years =  _.filter(vm.yearsCopy, function (y) {
                return y.id <= latest.getFullYear();
            });
            vm.selectedYear = latest.getFullYear();
            vm.selectedMonth = 12;
        }
        if (year.id === latest.getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id <= latest.getMonth() + 1;
            });
            vm.selectedMonth = vm.selectedMonth <= latest.getMonth() + 1 ? vm.selectedMonth : latest.getMonth() + 1;
        } else if (year.id === 2017) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= 3;
            });
            vm.selectedMonth = vm.selectedMonth >= 3 ? vm.selectedMonth : 3;
        } else {
            vm.months = vm.monthsCopy;
        }
        vm.updateSelectedDate();
    };

    vm.onSelectLocation = function (item, level) {
        return locationsService.onSelectLocation(item, level, locationsCache, vm);
    };

    vm.isLocationVisible = function (index) {
        return locationsService.locationTypeIsVisible(vm.selectedLocations, index);
    };

    vm.getLocationPlaceholder = function (locationTypes) {
        return locationsService.getLocationPlaceholder(locationTypes, true);
    };

    vm.getLocationsForLevel = function (level) {
        return locationsService.getLocations(level, locationsCache, vm.selectedLocations, true);
    };

    vm.accessToAllLocationsForLevel = function (locations) {
        var haveAccessToAllLocationsForLevel = true;
        window.angular.forEach(locations, function (location) {
            if (!location.user_have_access) {
                haveAccessToAllLocationsForLevel = false;
            }
        });
        return haveAccessToAllLocationsForLevel;
    };

    vm.userLocationIdIsNull = function () {
        return ["null", "undefined"].indexOf(vm.userLocationId) !== -1;
    };

    vm.preventShowingAllOption = function (locations) {
        return !vm.userLocationIdIsNull() && !vm.accessToAllLocationsForLevel(locations);
    };

    vm.isLocationDisabled = function (level) {
        return locationsService.isLocationDisabled(level, vm);
    };

    vm.message = false;

    vm.submitForm = function (csrfToken) {
        vm.message = false;
        var taskConfig = {
            'csrfmiddlewaretoken': csrfToken,
            'location': vm.selectedLocationId,
            'month': vm.selectedMonth,
            'year': vm.selectedYear,
            'indicator': vm.selectedIndicator,
        };
        downloadService.downloadCasData(taskConfig).then(function (data) {
            if (data.message) {
                vm.message = true;
            } else {
                $window.open(data.report_link);
            }
        });
    };

    vm.showReassignmentMessage = function () {
        var utcSelectedDate = Date.UTC(vm.selectedDate.getFullYear(), vm.selectedDate.getMonth());
        return vm.selectedLocation && (Date.parse(vm.selectedLocation.archived_on) <= utcSelectedDate || Date.parse(vm.selectedLocation.deprecates_at) > utcSelectedDate);
    };
}

CasExportController.$inject = ['$window', '$location', 'locationHierarchy', 'locationsService', 'downloadService', 'userLocationId', 'isAlertActive'];

window.angular.module('icdsApp').directive("casExport", function () {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'cas-export.directive'),
        controller: CasExportController,
        controllerAs: "$ctrl",
    };
});
