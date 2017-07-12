/* global moment, _ */


function MonthModalController($location, $uibModalInstance) {
    var vm = this;

    vm.days = [];

    window.angular.forEach(_.range(1,32), function(key) {
        vm.days.push({
            name: key,
            id: key,
        });
    });

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
    vm.selectedDay = $location.search()['day'] !== void(0) ? $location.search()['day'] : new Date().getDay();

    vm.apply = function() {
        $uibModalInstance.close({
            month: vm.selectedMonth,
            year: vm.selectedYear,
            day: vm.selectedDay,
        });
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function MonthFilterController($scope, $location, $uibModal, storageService) {
    var vm = this;

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
            $location.search('day', data['day']);
            storageService.setKey('search', $location.search());
            $scope.$emit('filtersChange');
        });
    };
}

MonthFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService'];
MonthModalController.$inject = ['$location', '$uibModalInstance'];

window.angular.module('icdsApp').directive("monthFilter", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
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
