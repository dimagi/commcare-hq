function AdditionalModalController($location, $uibModalInstance, filters, genders, ages, agesServiceDeliveryDashboard, haveAccessToFeatures) {
    var vm = this;
    vm.filters = filters;

    vm.genders = window.angular.copy(genders);

    vm.ages = window.angular.copy(ages);
    vm.agesServiceDeliveryDashboard = window.angular.copy(agesServiceDeliveryDashboard);
    vm.haveAccessToFeatures = haveAccessToFeatures;

    if (!vm.haveAccessToFeatures) {
        var path = $location.path();
        if (path.indexOf('underweight_children') !== -1 || path.indexOf('wasting') !== -1 || path.indexOf('stunting') !== -1) {
            vm.ages.pop();
            if (path.indexOf('wasting') !== -1 || path.indexOf('stunting') !== -1) {
                vm.ages.splice(1, 1);
            }
        }
    }

    vm.selectedGender = $location.search()['gender'] !== void(0) ? $location.search()['gender'] : '';
    vm.selectedAge = $location.search()['age'] !== void(0) ? $location.search()['age'] : '';
    vm.selectedAgeSDD = $location.search()['ageSDD'] !== void(0) ? $location.search()['ageSDD'] : '0_3';

    vm.apply = function () {
        hqImport('analytix/js/google').track.event('Additional Filter', 'Filter Changed', '');
        $uibModalInstance.close({
            gender: vm.selectedGender,
            age: vm.selectedAge,
            ageSDD: vm.selectedAgeSDD,
        });
    };

    vm.reset = function () {
        vm.selectedAge = '';
        vm.selectedGender = '';
        vm.selectedAgeSDD = '0_3';
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function AdditionalFilterController($scope, $location, $uibModal, storageService) {
    var vm = this;

    var page = $location.path().split('/')[1];
    if (storageService.getKey('last_page') !== page) {
        if (storageService.getKey('last_page') !== '') {
            $location.search('gender', null);
            $location.search('age', null);
            $location.search('ageSDD', null);
        }
        storageService.setKey('last_page', page);
    }

    vm.selectedGender = $location.search()['gender'] !== void(0) ? $location.search()['gender'] : '';
    vm.selectedAge = $location.search()['age'] !== void(0) ? $location.search()['age'] : '';
    vm.selectedAgeSDD = $location.search()['ageSDD'] !== void(0) ? $location.search()['ageSDD'] : '0_3';
    var filtersObjects = [];
    if (vm.filters && vm.filters.indexOf('gender') === -1) {
        filtersObjects.push({ label: 'Gender', value: vm.selectedGender });
    }
    if (vm.filters && vm.filters.indexOf('age') === -1) {
        filtersObjects.push({ label: 'Age', value: vm.selectedAge });
    }
    if (vm.filters && vm.filters.indexOf('ageServiceDeliveryDashboard') === -1) {
        filtersObjects.push({ label: 'AgeSDD', value: vm.selectedAgeSDD });
    }

    vm.getPlaceholder = function () {
        var placeholder = '';
        filtersObjects.forEach(function (filterObject) {
            if (filterObject.value) {
                var val = filterObject.value;
                if (filterObject.label === 'Age') val += ' m';
                placeholder += filterObject.label + ': ' + val + ' ';
                if (filterObject.label === 'AgeSDD') {
                    placeholder = filterObject.value === '0_3' ? '0-3 years (0-1095 days)' : '3-6 years (1096-2190 days)';
                }
            }
        });

        if (!placeholder) {
            return 'Additional Filter';
        } else {
            return placeholder;
        }
    };

    vm.open = function () {
        var modalInstance = $uibModal.open({
            animation: vm.animationsEnabled,
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'additionalModalContent.html',
            controller: AdditionalModalController,
            controllerAs: '$ctrl',
            resolve: {
                filters: function () {
                    return vm.filters;
                },
            },
        });

        modalInstance.result.then(function (data) {
            $location.search('gender', data['gender']);
            $location.search('age', data['age']);
            $location.search('ageSDD', data['ageSDD']);
            $scope.$emit('filtersChange');
        });
    };
}

AdditionalFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService'];
AdditionalModalController.$inject = ['$location', '$uibModalInstance', 'filters', 'genders', 'ages', 'agesServiceDeliveryDashboard', 'haveAccessToFeatures'];

window.angular.module('icdsApp').directive("additionalFilter", function () {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict: 'E',
        scope: {
            filters: '=',
        },
        bindToController: true,
        require: 'ngModel',
        templateUrl: url('icds-ng-template', 'additional-filter'),
        controller: AdditionalFilterController,
        controllerAs: "$ctrl",
    };
});
