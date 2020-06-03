/* global moment, _ */

function MonthModalController($location, $uibModalInstance, dateHelperService) {
    var vm = this;

    vm.months = [];
    vm.years = [];
    vm.monthsCopy = [];
    vm.showMessage = false;
    var reportStartDates = dateHelperService.getReportStartDates();

    var isSDD =  $location.path().indexOf('service_delivery_dashboard') !== -1;

    var startYear = dateHelperService.getStartingYear(isSDD);

    var currentDate = new Date();
    var maxYear = dateHelperService.checkAndGetValidDate(currentDate).getFullYear();

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


    var fullselectedDate = new Date(vm.selectedYear, vm.selectedMonth - 1);

    if (isSDD && (fullselectedDate < reportStartDates['sdd'])) {
        vm.showMessage = true;
        vm.selectedYear = maxYear;
    }


    var customMonths = dateHelperService.getCustomAvailableMonthsForReports(vm.selectedYear,
        vm.selectedMonth,
        vm.monthsCopy,
        isSDD);


    vm.months = customMonths.months;
    vm.selectedMonth = customMonths.selectedMonth;

    vm.apply = function () {
        hqImport('analytix/js/google').track.event('Date Filter', 'Date Changed', '');
        $uibModalInstance.close({
            month: vm.selectedMonth,
            year: vm.selectedYear,
        });
    };

    vm.onSelectYear = function (item) {

        var customMonths = dateHelperService.getCustomAvailableMonthsForReports(item.id,
            vm.selectedMonth,
            vm.monthsCopy,
            isSDD);

        vm.months = customMonths.months;
        vm.selectedMonth = customMonths.selectedMonth;
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function MonthFilterController($scope, $location, $uibModal, storageService, dateHelperService, isMobile) {
    var vm = this;

    // used by mobile dashboard
    var isSDD =  $location.path().indexOf('service_delivery_dashboard') !== -1;
    vm.startYear = dateHelperService.getStartingYear(isSDD);
    vm.startMonth = dateHelperService.getStartingMonth(isSDD);
    vm.maxMonth = dateHelperService.checkAndGetValidDate(new Date()).getMonth() + 1;
    vm.maxYear = dateHelperService.checkAndGetValidDate(new Date()).getFullYear();

    vm.selectedDate = dateHelperService.getSelectedDate();
    if (isSDD && vm.selectedDate < dateHelperService.getReportStartDates()['sdd']) {
        vm.selectedDate = dateHelperService.checkAndGetValidDate(new Date());
    }
    vm.currentYear = new Date().getFullYear();
    vm.getPlaceholder = function () {
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

    $scope.$on('reset_filter_data', function () {
        $scope.$broadcast('reset_date',{});
        vm.selectedDate = dateHelperService.checkAndGetValidDate(new Date());
    });
    // end mobile only helpers

    vm.init = function () {
        var selectedDate = dateHelperService.getValidSelectedDate();

        if ($location.path().indexOf('service_delivery_dashboard') !== -1 &&
            selectedDate < new Date(2019, 1) && !isMobile) {
            vm.open();
        }

    };

    vm.init();
}

MonthFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService', 'dateHelperService', 'isMobile'];
MonthModalController.$inject = ['$location', '$uibModalInstance', 'dateHelperService'];

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
