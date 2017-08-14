/* global moment, _ */


function MonthModalController($location, $uibModalInstance) {
    var vm = this;

    vm.months = [];
    vm.years = [];

    window.angular.forEach(moment.months(), function(key, value) {
        vm.months.push({
            name: key,
            id: value + 1,
        });
    });

    for (var year=2014; year <= new Date().getFullYear(); year++ ) {
        vm.years.push({
            name: year,
            id: year,
        });
    }

    vm.selectedMonth = $location.search()['month'] !== void(0) ? $location.search()['month'] : new Date().getMonth() + 1;
    vm.selectedYear = $location.search()['year'] !== void(0) ? $location.search()['year'] : new Date().getFullYear();

    vm.apply = function() {
        $uibModalInstance.close({
            month: vm.selectedMonth,
            year: vm.selectedYear,
        });
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function MonthFilterController($scope, $location, $uibModal, storageService) {
    var vm = this;

    vm.getPlaceholder = function() {
        var month = $location.search().month;
        var year = $location.search().year;
        var formattedMonth = moment(month, 'MM').format('MMMM');

        if (month && year) {
            return formattedMonth + ' ' + year;
        } else {
            return 'Search by Month/Year';
        }
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
}

MonthFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService'];
MonthModalController.$inject = ['$location', '$uibModalInstance'];

window.angular.module('icdsApp').directive("monthFilter", function() {
    var url = hqImport('hqwebapp/js/initial_page_data.js').reverse;
    return {
        restrict:'E',
        scope: {
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'month-filter'),
        controller: MonthFilterController,
        controllerAs: "$ctrl",
    };
});
