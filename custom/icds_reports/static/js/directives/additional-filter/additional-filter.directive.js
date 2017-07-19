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
        {id: '0', name: '0 months'},
        {id: '6', name: '6 months'},
        {id: '12', name: '12 months'},
        {id: '24', name: '24 months'},
        {id: '36', name: '36 months'},
        {id: '48', name: '48 months'},
        {id: '60', name: '60 months'},
        {id: '72', name: '72 months'},
    ];

    vm.selectedGender = $location.search()['gender'] !== void(0) ? $location.search()['gender'] : '';
    vm.selectedAge = $location.search()['age'] !== void(0) ? $location.search()['age'] : '';

    vm.apply = function() {
        $uibModalInstance.close({
            gender: vm.selectedGender,
            age: vm.selectedAge,
        });
    };

    vm.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
}

function AdditionalFilterController($scope, $location, $uibModal) {
    var vm = this;

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

AdditionalFilterController.$inject = ['$scope', '$location', '$uibModal' ];
AdditionalModalController.$inject = ['$location', '$uibModalInstance', 'filters'];

window.angular.module('icdsApp').directive("additionalFilter", function() {
    var url = hqImport('hqwebapp/js/urllib.js').reverse;
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
