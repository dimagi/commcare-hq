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

    vm.apply = function () {
        hqImport('analytix/js/google').track.event('Additional Filter', 'Filter Changed', '');
        $uibModalInstance.close({
            gender: vm.selectedGender,
            age: vm.selectedAge,
        });
    };

    vm.reset = function () {
        vm.selectedAge = '';
        vm.selectedGender = '';
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
        }
        storageService.setKey('last_page', page);
    }

    vm.selectedGender = $location.search()['gender'] !== void(0) ? $location.search()['gender'] : '';
    vm.selectedAge = $location.search()['age'] !== void(0) ? $location.search()['age'] : '';
    var filtersObjects = [];
    if (vm.filters && vm.filters.indexOf('gender') === -1) {
        filtersObjects.push({ label: 'Gender', value: vm.selectedGender });
    }
    if (vm.filters && vm.filters.indexOf('age') === -1) {
        filtersObjects.push({ label: 'Age', value: vm.selectedAge });
    }

    vm.getPlaceholder = function () {
        var placeholder = '';
        filtersObjects.forEach(function (filterObject) {
            if (filterObject.value) {
                var val = filterObject.value;
                if (filterObject.label === 'Age') val += ' m';
                placeholder += filterObject.label + ': ' + val + ' ';
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
