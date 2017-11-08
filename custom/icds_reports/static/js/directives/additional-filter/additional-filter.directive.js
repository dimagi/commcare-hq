function AdditionalModalController($location, $uibModalInstance, filters) {
    var vm = this;
    vm.filters = filters;

    vm.genders = [
        {id: '', name: 'All'},
        {id: 'M', name: 'Male'},
        {id: 'F', name: 'Female'},
    ];

    vm.ages = [
        {id: '', name: 'All'},
        {id: '6', name: '0-6 months'},
        {id: '12', name: '6-12 months'},
        {id: '24', name: '12-24 months'},
        {id: '36', name: '24-36 months'},
        {id: '48', name: '36-48 months'},
        {id: '60', name: '48-60 months'},
        {id: '72', name: '60-72 months'},
    ];

    var path = $location.path();
    if (path.indexOf('underweight_children') !== -1 || path.indexOf('wasting') !== -1 || path.indexOf('stunting') !== -1) {
        vm.ages.pop();
        if (path.indexOf('wasting') !== -1 || path.indexOf('stunting') !== -1) {
            vm.ages.splice(1,1);
        }
    }

    vm.selectedGender = $location.search()['gender'] !== void(0) ? $location.search()['gender'] : '';
    vm.selectedAge = $location.search()['age'] !== void(0) ? $location.search()['age'] : '';

    vm.apply = function() {
        $uibModalInstance.close({
            gender: vm.selectedGender,
            age: vm.selectedAge,
        });
    };

    vm.reset = function() {
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
    if (vm.filters.indexOf('gender') === -1) {
        filtersObjects.push({ label: 'Gender', value: vm.selectedGender });
    }
    if (vm.filters.indexOf('age') === -1) {
        filtersObjects.push({ label: 'Age', value: vm.selectedAge });
    }


    vm.getPlaceholder = function() {
        var placeholder = '';
        filtersObjects.forEach(function(filterObject) {
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
                filters: function() {
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
AdditionalModalController.$inject = ['$location', '$uibModalInstance', 'filters'];

window.angular.module('icdsApp').directive("additionalFilter", function() {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        restrict:'E',
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
