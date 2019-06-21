/* global moment */

function CasExportController($window, $location, locationHierarchy, locationsService, downloadService, userLocationId) {
    var vm = this;

    vm.months = [];
    vm.monthsCopy = [];
    vm.years = [];
    vm.yearsCopy = [];

    vm.selectedLocation = userLocationId;
    vm.selectedIndicator = null;

    locationsService.getRootLocations().then(function (data) {
        vm.locations = data.locations;
    });
    var now = moment();
    if (now.date() <= 7) {
        now.subtract(2, 'months');
    } else {
        now.subtract(1, 'months');
    }

    vm.selectedMonth = now.month() + 1;
    vm.selectedYear = now.year();

    window.angular.forEach(moment.months(), function (key, value) {
        vm.monthsCopy.push({
            name: key,
            id: value + 1,
        });
    });

    if (vm.selectedYear === new Date().getFullYear()) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id < new Date().getMonth() || (month.id === new Date().getMonth() && moment().date() > 7);
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
    vm.filterOptions = [
        {label: 'Data not Entered for weight (Unweighed)', id: 'unweighed'},
        {label: 'Data not Entered for height (Unmeasured)', id: 'umeasured'},
        {label: 'Severely Underweight', id: 'severely_underweight'},
        {label: 'Moderately Underweight', id: 'moderately_underweight'},
        {label: 'Normal (weight-for-age)', id: 'normal_wfa'},
        {label: 'Severely Stunted', id: 'severely_stunted'},
        {label: 'Moderately Stunted', id: 'moderately_stunted'},
        {label: 'Normal (height-for-age)', id: 'normal_hfa'},
        {label: 'Severely Wasted', id: 'severely_wasted'},
        {label: 'Moderately Wasted', id: 'moderately_wasted'},
        {label: 'Normal (weight-for-height)', id: 'normal_wfh'},
    ];

    vm.indicators = [
        {id: 1, name: 'Child'},
        {id: 2, name: 'Pregnant and Lactating Women'},
        {id: 3, name: 'AWC'},
    ];

    vm.allFiltersSelected = function () {
        return vm.selectedLocation !== null && vm.selectedMonth !== null && vm.selectedYear !== null && vm.selectedIndicator !== null;
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
    };
    vm.message = false;

    vm.submitForm = function (csrfToken) {
        vm.message = false;
        var taskConfig = {
            'csrfmiddlewaretoken': csrfToken,
            'location': vm.selectedLocation,
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

}

CasExportController.$inject = ['$window', '$location', 'locationHierarchy', 'locationsService', 'downloadService', 'userLocationId'];

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
