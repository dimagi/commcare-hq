function MobileFiltersController($scope) {
    const MONTH = 'month';
    const LOCATION = 'location';
    $scope.selectedTab = MONTH;
    $scope.closeFilters = function () {
        $scope.$emit('closeFilterMenu', {});
    };
    $scope.selectMonthTab = function () {
        $scope.selectedTab = MONTH;
    };
    $scope.selectLocationTab = function () {
        $scope.selectedTab = LOCATION;
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
