var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function DataPeriodModalController($location, $uibModalInstance, filters, dataPeriods, haveAccessToFeatures) {
    var vm = this;
    vm.filters = filters;

    vm.dataPeriods = window.angular.copy(dataPeriods);
    vm.haveAccessToFeatures = haveAccessToFeatures;

    vm.selectedDataPeriod = $location.search()['data_period'] !== void(0) ? $location.search()['data_period'] : 'month';

    vm.apply = function () {
        hqImport('analytix/js/google').track.event('Data Period Filter', 'Data Period Changed', '');
        $uibModalInstance.close({
            data_period: vm.selectedDataPeriod,
        });
    };

    vm.reset = function () {
        vm.selectedDataPeriod = 'month';
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function DataPeriodFilterController($scope, $location, $uibModal, storageService, dataPeriods) {
    var vm = this;
    vm.dataPeriods = dataPeriods;
    vm.showDataPeriodsFilter = false;

    vm.selectedDataPeriod = $location.search()['data_period'] !== void(0) ? $location.search()['data_period'] : 'month';

    if (vm.filters && vm.filters.indexOf('data_period') === -1) {
        vm.showDataPeriodsFilter = true;
    }

    vm.getPlaceholder = function () {
        for (var i = 0; i < dataPeriods.length; i++) {
            if (dataPeriods[i]['id'] == vm.selectedDataPeriod) {
                return dataPeriods[i]['name'];
            }
        }
    };

    vm.open = function () {
        var modalInstance = $uibModal.open({
            animation: vm.animationsEnabled,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'dataPeriodModalContent.html',
            controller: DataPeriodModalController,
            controllerAs: '$ctrl',
            resolve: {
                filters: function () {
                    return vm.filters;
                },
            },
        });

        modalInstance.result.then(function (data) {
            $location.search('data_period', data['data_period']);
            if (data['data_period'] == 'month') {
                $location.search('quarter', null);
            }
            $scope.$emit('filtersChange');
        });
    };

    vm.reset = function () {
        vm.selectedDataPeriod = 'month';
    };
}

DataPeriodFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService', 'dataPeriods'];
DataPeriodModalController.$inject = ['$location', '$uibModalInstance', 'filters', 'dataPeriods', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive("dataperiodFilter", function () {
    return {
        restrict: 'E',
        scope: {
            filters: '=',
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'data-period-filter'),
        controller: DataPeriodFilterController,
        controllerAs: "$ctrl",
    };
});
