
function FilterOpenerController($scope) {
    $scope.openFilters = function () {
        $scope.$broadcast('openFilterMenu');
    };
}

FilterOpenerController.$inject = ['$scope'];

window.angular.module('icdsApp').directive("filterOpener",  ['templateProviderService', function (templateProviderService) {
    return {
        restrict: 'E',
        bindToController: true,
        templateUrl: function () {
            return templateProviderService.getTemplate('filter-opener.directive');
        },
        controller: FilterOpenerController,
    };
}]);
