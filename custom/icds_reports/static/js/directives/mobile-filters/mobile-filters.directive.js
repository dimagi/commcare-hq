function MobileFiltersController($scope) {
    // mobile only
    $scope.closeFilters = function () {
        $scope.$emit('closeFilterMenu', {});
    };
}

MobileFiltersController.$inject = ['$scope'];

window.angular.module('icdsApp').directive("mobileFilters", ['templateProviderService', function (templateProviderService) {
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
            return templateProviderService.getTemplate('mobile-filters.directive');
        },
        controller: MobileFiltersController,
        controllerAs: "$ctrl",
    };
}]);
