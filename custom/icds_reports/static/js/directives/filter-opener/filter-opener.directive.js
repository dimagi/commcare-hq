
function FilterOpenerController($scope, $rootScope) {
    $scope.openFilters = function () {
        $rootScope.$broadcast('openFilterMenu');
    };
}

FilterOpenerController.$inject = ['$scope', '$rootScope'];

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
