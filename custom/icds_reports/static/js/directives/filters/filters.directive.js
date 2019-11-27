function FiltersController($scope) {
    // mobile only
    $scope.closeFilters = function () {
        $scope.$emit('closeFilterMenu', {});
    };
}

FiltersController.$inject = ['$scope'];

window.angular.module('icdsApp').directive("filters", ['templateProviderService', function (templateProviderService) {
    return {
        restrict:'E',
        scope: {
            data: '=',
            filters: '=',
            selectedLocations: '=',
            isOpenModal: '=?',
        },
        bindToController: true,
        templateUrl: function () {
            return templateProviderService.getTemplate('filters');
        },
        controller: FiltersController,
        controllerAs: "$ctrl",
    };
}]);
