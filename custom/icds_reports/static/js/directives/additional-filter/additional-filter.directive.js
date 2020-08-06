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

function AdditionalFilterController($scope, $location, $uibModal, storageService, genders, ages) {
    var vm = this;
    vm.genders = genders;
    vm.ages = ages;
    vm.showGenderFilter = false;
    vm.showAgeFilter = false;

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
    vm.$onInit = function () {
        // eg:vm.filters = ['gender', 'age']
        // this array has filters that are not to be shown. so if 'gender' is not in array, it can be shown.
        if (vm.filters && vm.filters.indexOf('gender') === -1) {
            vm.showGenderFilter = true;
            filtersObjects.push({ label: 'Gender', value: vm.selectedGender });
        }
        if (vm.filters && vm.filters.indexOf('age') === -1) {
            vm.showAgeFilter = true;
            filtersObjects.push({ label: 'Age', value: vm.selectedAge });
        }
    }

    vm.getPlaceholder = function () {
        var placeholder = '';
        filtersObjects.forEach(function (filterObject) {
            if (filterObject.value) {
                var val = filterObject.value;
                if (filterObject.label === 'Age') {
                    val += ' m';
                }
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

    vm.reset = function () {
        vm.selectedAge = '';
        vm.selectedGender = '';
    };

    // used only in mobile dashboard
    vm.selectedFilterType = '';

    vm.selectedGenderName = function () {
        for (var i = 0; i < vm.genders.length; i++) {
            if (vm.genders[i].id === vm.selectedGender) {
                return vm.genders[i].name;
            }
        }
    };

    vm.selectedAgeGroupName = function () {
        for (var i = 0; i < vm.ages.length; i++) {
            if (vm.ages[i].id === vm.selectedAge) {
                return vm.ages[i].name;
            }
        }
    };

    $scope.$on('request_filter_data', function () {
        $scope.$emit('filter_data', {
            'hasAdditionalFilterData': true,
            'gender': vm.selectedGender,
            'age': vm.selectedAge,
        });
    });

    $scope.$on('reset_filter_data', function () {
        $scope.$broadcast('reset_date',{});
        vm.reset();
    });
    // end mobile dashboard helpers
}

AdditionalFilterController.$inject = ['$scope', '$location', '$uibModal', 'storageService', 'genders', 'ages'];
AdditionalModalController.$inject = ['$location', '$uibModalInstance', 'filters', 'genders', 'ages', 'agesServiceDeliveryDashboard', 'haveAccessToFeatures'];

window.angular.module('icdsApp').component("additionalFilter", {
    bindings: {
        filters: '<',
    },
    require: 'ngModel',
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('additional-filter');
    }],
    controller: AdditionalFilterController,
    controllerAs: "$ctrl",
});
