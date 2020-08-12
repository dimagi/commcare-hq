/* global moment, _ */

function MonthModalController($location, $uibModalInstance, dateHelperService, quartersOfYear) {
    var vm = this;

    vm.months = [];
    vm.years = [];
    vm.monthsCopy = [];
    vm.showMessage = false;
    vm.showPPDMessage = false; // this is set to true if the selected data is less than PPD start date
    vm.quartersOfYear = window.angular.copy(quartersOfYear);
    vm.quartersOfYearDisplayed = [];
    var reportStartDates = dateHelperService.getReportStartDates();

    var isSDD =  $location.path().indexOf('service_delivery_dashboard') !== -1;
    var isPPD =  $location.path().indexOf('poshan_progress_dashboard') !== -1;
    var isQuarterlyDataPeriodSelected = $location.search()['data_period'] === 'quarter';
    vm.isQuarterlyDataPeriodSelected = isQuarterlyDataPeriodSelected;
    vm.isPPD = isPPD;

    var startYear = dateHelperService.getStartingYear(isSDD, isPPD);

    var currentDate = new Date();
    var maxYear = dateHelperService.checkAndGetValidDate(currentDate).getFullYear();
    if (isPPD && isQuarterlyDataPeriodSelected) {
        // max year in date filter is set based upon the latest quarter for which data is available
        maxYear = dateHelperService.getLatestQuarterAvailable()['year'];
    }

    window.angular.forEach(moment.months(), function (key, value) {
        vm.monthsCopy.push({
            name: key,
            id: value + 1,
        });
    });


    for (var year = startYear; year <= maxYear; year++) {
        vm.years.push({
            name: year,
            id: year,
        });
    }

    vm.selectedMonth = dateHelperService.getSelectedMonth();
    vm.selectedYear = dateHelperService.getSelectedYear();

    if (isPPD && isQuarterlyDataPeriodSelected) {
        var selectedQuarterAndYear = dateHelperService.getSelectedQuarterAndYear();
        vm.selectedQuarter = selectedQuarterAndYear['quarter'];
        vm.selectedYear = selectedQuarterAndYear['year'];
    }


    var fullselectedDate = new Date(vm.selectedYear, vm.selectedMonth - 1);

    if (isSDD && (fullselectedDate < reportStartDates['sdd'])) {
        vm.showMessage = true;
        vm.selectedYear = maxYear;
    }

    if (isPPD && (fullselectedDate < reportStartDates['ppd']) && !isQuarterlyDataPeriodSelected) {
        vm.showPPDMessage = true;
        vm.selectedYear = maxYear;
    }


    var customMonths = dateHelperService.getCustomAvailableMonthsForReports(vm.selectedYear,
        vm.selectedMonth,
        vm.monthsCopy,
        isSDD, isPPD);


    vm.months = customMonths.months;
    vm.selectedMonth = customMonths.selectedMonth;

    if (isPPD && isQuarterlyDataPeriodSelected) {
        var customQuarters = dateHelperService.getCustomAvailableQuarters(vm.selectedYear,
            vm.selectedQuarter,
            vm.quartersOfYear);

        vm.quartersOfYearDisplayed = customQuarters['quarters'];
        vm.selectedQuarter = customQuarters['selectedQuarter'];
    }

    vm.apply = function () {
        hqImport('analytix/js/google').track.event('Date Filter', 'Date Changed', '');
        if (isPPD && isQuarterlyDataPeriodSelected) {
            $uibModalInstance.close({
                quarter: vm.selectedQuarter,
                year: vm.selectedYear,
            });
        } else {
            $uibModalInstance.close({
                month: vm.selectedMonth,
                year: vm.selectedYear,
            });
        }
    };

    vm.onSelectYear = function (item) {
        if (isPPD && isQuarterlyDataPeriodSelected) {
            var customQuarters = dateHelperService.getCustomAvailableQuarters(item.id,
                vm.selectedQuarter,
                vm.quartersOfYear);

            vm.quartersOfYearDisplayed = customQuarters['quarters'];
            vm.selectedQuarter = customQuarters['selectedQuarter'];
        } else {
            var customMonths = dateHelperService.getCustomAvailableMonthsForReports(item.id,
                vm.selectedMonth,
                vm.monthsCopy,
                isSDD, isPPD);

            vm.months = customMonths.months;
            vm.selectedMonth = customMonths.selectedMonth;
        }
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function MonthFilterController($scope, $location, $uibModal, storageService, dateHelperService, isMobile, quartersOfYear) {
    var vm = this;

    // used by mobile dashboard
    var isSDD =  $location.path().indexOf('service_delivery_dashboard') !== -1;
    var isPPD =  $location.path().indexOf('poshan_progress_dashboard') !== -1;
    vm.startYear = dateHelperService.getStartingYear(isSDD, isPPD);
    vm.startMonth = dateHelperService.getStartingMonth(isSDD, isPPD);
    vm.maxMonth = dateHelperService.checkAndGetValidDate(new Date()).getMonth() + 1;
    vm.maxYear = dateHelperService.checkAndGetValidDate(new Date()).getFullYear();

    // if moved out of PPD, then data_period and quarter is removed from url params
    if (isPPD) {
        var isQuarterlyDataPeriodSelected = $location.search()['data_period'] === 'quarter';
        var isQuarterSelected = $location.search()['quarter'] || false;
        vm.quartersOfYear = window.angular.copy(quartersOfYear);
    } else {
        $location.search('data_period', null);
        $location.search('quarter', null);
    }

    vm.selectedDate = dateHelperService.getSelectedDate();
    if (isSDD && vm.selectedDate < dateHelperService.getReportStartDates()['sdd']) {
        vm.selectedDate = dateHelperService.checkAndGetValidDate(new Date());
    }

    if (isPPD && vm.selectedDate < dateHelperService.getReportStartDates()['ppd']) {
        vm.selectedDate = dateHelperService.checkAndGetValidDate(new Date());
    }

    if (isPPD && isQuarterlyDataPeriodSelected) {
        if (!isQuarterSelected) {
            var selectedQuarterAndYear = dateHelperService.getQuarterAndYearFromDate(vm.selectedDate.getMonth(),
                vm.selectedDate.getFullYear());

            vm.selectedQuarter = selectedQuarterAndYear['quarter'];
            vm.selectedYear = selectedQuarterAndYear['year'];
        } else {
            selectedQuarterAndYear = dateHelperService.getSelectedQuarterAndYear();
            vm.selectedQuarter = selectedQuarterAndYear['quarter'];
            vm.selectedYear = selectedQuarterAndYear['year'];
        }
        dateHelperService.updateSelectedQuarter(vm.selectedQuarter, vm.selectedYear);
    }
    vm.currentYear = new Date().getFullYear();
    vm.getPlaceholder = function () {
        if (isPPD && isQuarterlyDataPeriodSelected) {
            var placeHolder = '';
            for (var i = 0; i < vm.quartersOfYear.length; i++) {
                if (vm.quartersOfYear[i]['id'] == vm.selectedQuarter) {
                    placeHolder += vm.quartersOfYear[i]['name'];
                    return placeHolder + ' ' + vm.selectedYear;
                }
            }
        }
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
            // Upon closing modal, params in the url are updated based on data_period type
            if (isPPD && isQuarterlyDataPeriodSelected) {
                dateHelperService.updateSelectedQuarter(data['quarter'], data['year']);
            } else {
                dateHelperService.updateSelectedMonth(data['month'], data['year']);
            }
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

    $scope.$on('reset_filter_data', function () {
        $scope.$broadcast('reset_date',{});
        vm.selectedDate = dateHelperService.checkAndGetValidDate(new Date());
    });
    // end mobile only helpers

    vm.init = function () {
        var selectedDate = dateHelperService.getValidSelectedDate();

        // opening date filter if selected date is less than corresponding report start date
        if ((($location.path().indexOf('service_delivery_dashboard') !== -1 &&
            selectedDate < new Date(2019, 1)) ||
            (($location.path().indexOf('poshan_progress_dashboard') !== -1 &&
            selectedDate < new Date(2019, 3)) && !isQuarterlyDataPeriodSelected)) && !isMobile) {
            vm.open();
        }

    };

    vm.init();
}

MonthFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService', 'dateHelperService', 'isMobile', 'quartersOfYear'];
MonthModalController.$inject = ['$location', '$uibModalInstance', 'dateHelperService', 'quartersOfYear'];

window.angular.module('icdsApp').directive("monthFilter",  ['templateProviderService', function (templateProviderService) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
            isOpenModal: '=?',
            selectSddDate: '=?',
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
