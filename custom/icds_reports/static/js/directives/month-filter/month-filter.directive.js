/* global moment, _ */

function MonthModalController($location, $uibModalInstance) {
    var vm = this;

    vm.months = [];
    vm.years = [];
    vm.monthsCopy = [];
    vm.showMessage = false;
    var isSDD =  $location.path().indexOf('service_delivery_dashboard') !== -1;
    var startDate = $location.path().indexOf('service_delivery_dashboard') === -1 ? 2017 : 2019;

    window.angular.forEach(moment.months(), function(key, value) {
        vm.monthsCopy.push({
            name: key,
            id: value + 1,
        });
    });


    for (var year = startDate; year <= new Date().getFullYear(); year++) {
        vm.years.push({
            name: year,
            id: year,
        });
    }

    vm.selectedMonth = $location.search()['month'] !== void(0) ? parseInt($location.search()['month']) : new Date().getMonth() + 1;
    vm.selectedYear = $location.search()['year'] !== void(0) ? parseInt($location.search()['year']) : new Date().getFullYear();

    if(isSDD && (vm.selectedYear<2019 || (vm.selectedYear==2019 && vm.selectedMonth==1))){
        vm.showMessage = true;
        vm.selectedYear = new Date().getFullYear();
        vm.selectedMonth = new Date().getMonth()+1;
    }

    if (vm.selectedYear === new Date().getFullYear()) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id <= new Date().getMonth() + 1;
        });

        if (startDate === 2019) {
            vm.months.shift();
        }
    } else if (startDate === 2019 && vm.selectedYear === 2019) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id >= 2;
        });
    } else if (vm.selectedYear === 2017) {
        vm.months = _.filter(vm.monthsCopy, function (month) {
            return month.id >= 3;
        });
    } else {
        vm.months = vm.monthsCopy;
    }

    vm.apply = function() {
        hqImport('analytix/js/google').track.event('Date Filter', 'Date Changed', '');
        $uibModalInstance.close({
            month: vm.selectedMonth,
            year: vm.selectedYear,
        });
    };

    vm.onSelectYear = function (item) {
        if (item.id === new Date().getFullYear()) {
            vm.months = _.filter(vm.monthsCopy, function(month) {
                return month.id <= new Date().getMonth() + 1;
            });

            if (startDate === 2019) {
                vm.months.shift();
            }
            
            vm.selectedMonth = vm.selectedMonth <= new Date().getMonth() + 1 ? vm.selectedMonth : new Date().getMonth() + 1;
        } else if (startDate === 2019 && vm.selectedYear === 2019) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= 2;
            });
        } else if (item.id === 2017) {
            vm.months = _.filter(vm.monthsCopy, function (month) {
                return month.id >= 3;
            });
            vm.selectedMonth = vm.selectedMonth >= 3 ? vm.selectedMonth : 3;
        } else {
            vm.months = vm.monthsCopy;
        }
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function MonthFilterController($scope, $location, $uibModal, storageService) {
    var vm = this;

    vm.getPlaceholder = function() {

        var now = moment().utc();

        var month = $location.search().month || now.month() + 1;
        var year = $location.search().year || now.year();
        var formattedMonth = moment(month, 'MM').format('MMMM');
        return formattedMonth + ' ' + year;
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
            $location.search('month', data['month']);
            $location.search('year', data['year']);
            storageService.setKey('search', $location.search());
            $scope.$emit('filtersChange');
        });
    };

    vm.init = function() {
            var month = $location.search()['month'];
            var year = $location.search()['year'];
            var displayModal = true;

            if(year > 2019 || (year==2019  &&  month>1)){
                displayModal = false;
            }

            if($location.path().indexOf('service_delivery_dashboard') !== -1
                && displayModal){
                vm.open();
            }
    }

    vm.init();
}

MonthFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService'];
MonthModalController.$inject = ['$location', '$uibModalInstance'];

window.angular.module('icdsApp').directive("monthFilter", function() {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict:'E',
        scope: {
            isOpenModal: '=?',
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'month-filter'),
        controller: MonthFilterController,
        controllerAs: "$ctrl",
    };
});
