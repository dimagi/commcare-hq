/* global moment, _ */

function MonthModalController($location, $uibModalInstance, dateHelperService, haveAccessToFeatures) {
    var vm = this;

    vm.months = [];
    vm.years = [];
    vm.monthsCopy = [];
    vm.showMessage = false;
    var reportStartDates = {
        'sdd': new Date(2019, 1),
        'adolescent_girls': new Date(2019, 3),
    };

    var isSDD =  $location.path().indexOf('service_delivery_dashboard') !== -1;
    var isAdolescentGirls =  $location.path().indexOf('demographics/adolescent_girls') !== -1;


    var startYear = 2017;


    if (isSDD) {
        startYear = reportStartDates['sdd'].getFullYear();
    } else if (isAdolescentGirls && haveAccessToFeatures) {
        startYear = reportStartDates['adolescent_girls'].getFullYear();
    }



    window.angular.forEach(moment.months(), function(key, value) {
        vm.monthsCopy.push({
            name: key,
            id: value + 1,
        });
    });


    for (var year = startYear; year <= new Date().getFullYear(); year++) {
        vm.years.push({
            name: year,
            id: year,
        });
    }

    vm.selectedMonth = dateHelperService.getSelectedMonth();
    vm.selectedYear = dateHelperService.getSelectedYear();


    var fullselectedDate = new Date(vm.selectedYear, vm.selectedMonth - 1);

    if (isSDD && (vm.selectedYear < 2019 || (vm.selectedYear === 2019 && vm.selectedMonth === 1))) {
        vm.showMessage = true;
        vm.selectedYear = new Date().getFullYear();
        vm.selectedMonth = new Date().getMonth() + 1;
    }

    if (haveAccessToFeatures && isAdolescentGirls && fullselectedDate < reportStartDates['adolescent_girls']) {
        vm.showAdolescentGirlMessage = true;
        vm.selectedYear = new Date().getFullYear();
        vm.selectedMonth = new Date().getMonth() + 1;
    }

    vm.months = vm.monthsCopy;

    if (vm.selectedYear === new Date().getFullYear()) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id <= new Date().getMonth() + 1;
        });

    } else {

        if (isSDD && vm.selectedYear === reportStartDates['sdd'].getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= reportStartDates['sdd'].getMonth() + 1;
            });
        }

        if (haveAccessToFeatures && isAdolescentGirls && vm.selectedYear === reportStartDates['adolescent_girls'].getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= reportStartDates['adolescent_girls'].getMonth() + 1;
            });
        }
        if (vm.selectedYear === 2017) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= 3;
            });
        }

    }

    vm.apply = function() {
        hqImport('analytix/js/google').track.event('Date Filter', 'Date Changed', '');
        $uibModalInstance.close({
            month: vm.selectedMonth,
            year: vm.selectedYear,
        });
    };

    vm.onSelectYear = function (item) {
        vm.months = vm.monthsCopy;
        if (item.id === new Date().getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id <= new Date().getMonth() + 1;
            });

            vm.selectedMonth = vm.selectedMonth <= new Date().getMonth() + 1 ? vm.selectedMonth : new Date().getMonth() + 1;
        } else {

            if (isSDD && vm.selectedYear === reportStartDates['sdd'].getFullYear()) {
                vm.months = _.filter(vm.monthsCopy, function (month) {
                    return month.id >= reportStartDates['sdd'].getMonth() + 1;
                });
                vm.selectedMonth = vm.selectedMonth >= reportStartDates['sdd'].getMonth() + 1 ?
                    vm.selectedMonth : reportStartDates['sdd'].getMonth() + 1;
            }

            if (haveAccessToFeatures && isAdolescentGirls && vm.selectedYear === reportStartDates['adolescent_girls'].getFullYear()) {
                vm.months = _.filter(vm.monthsCopy, function (month) {
                    return month.id >= reportStartDates['adolescent_girls'].getMonth() + 1;
                });
                vm.selectedMonth = vm.selectedMonth >= reportStartDates['adolescent_girls'].getMonth() + 1 ?
                    vm.selectedMonth : reportStartDates['adolescent_girls'].getMonth() + 1;

            }
            if (vm.selectedYear === 2017) {
                vm.months = _.filter(vm.monthsCopy, function (month) {
                    return month.id >= 3;
                });
                vm.selectedMonth = vm.selectedMonth >= 3 ? vm.selectedMonth : 3;
            }

        }
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function MonthFilterController($scope, $location, $uibModal, storageService, dateHelperService, haveAccessToFeatures) {
    var vm = this;

    // used by mobile dashboard
    vm.selectedDate = dateHelperService.getSelectedDate();
    vm.currentYear = new Date().getFullYear();
    vm.getPlaceholder = function() {
        return dateHelperService.getSelectedMonthDisplay();
    };

    vm.open = function () {
        var modalInstance = $uibModal.open({
            animation: vm.animationsEnabled,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'monthModalContent.html',
            controller: MonthModalController,
            controllerAs: '$ctrl',
            resolve: {
            },
        });

        modalInstance.result.then(function (data) {
            dateHelperService.updateSelectedMonth(data['month'], data['year']);
            storageService.setKey('search', $location.search());
            $scope.$emit('filtersChange');
        });
    };

    // mobile only helpers
    // update currently selected month from inner datepicker's events
    $scope.$on('date_picked', function (event, data) {
        vm.selectedDate = data.info;
    });

    // respond to requests for filter data with currently selected month
    $scope.$on('request_filter_data', function () {
        $scope.$emit('filter_data', {
            'hasDate': true,
            'date': vm.selectedDate,
            'month': vm.selectedDate.getMonth() + 1,
            'year': vm.selectedDate.getFullYear(),
        });
    });

    $scope.$on('reset_filter_data', function() {
        $scope.$broadcast('reset_date',{});
        vm.selectedDate = new Date();
    });
    // end mobile only helpers

    vm.init = function () {
        var selectedMonth = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selectedYear =  parseInt($location.search()['year']) || new Date().getFullYear();

        var selectDate = new Date(selectedYear, selectedMonth - 1);

        if ($location.path().indexOf('service_delivery_dashboard') !== -1 && selectDate < new Date(2019, 1)) {
            vm.open();
        }

        if (haveAccessToFeatures && $location.path().indexOf('demographics/adolescent_girls') !== -1 && selectDate < new Date(2019, 3)) {
            vm.open();
        }
    };

    vm.init();
}

MonthFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService', 'dateHelperService', 'haveAccessToFeatures'];
MonthModalController.$inject = ['$location', '$uibModalInstance', 'dateHelperService', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive("monthFilter",  ['templateProviderService', function (templateProviderService) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict:'E',
        scope: {
            isOpenModal: '=?',
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: function () {
            return templateProviderService.getTemplate('month-filter');
        },
        controller: MonthFilterController,
        controllerAs: "$ctrl",
    };
}]);
