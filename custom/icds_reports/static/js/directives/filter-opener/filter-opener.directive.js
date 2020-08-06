
function FilterOpenerController($scope, $rootScope) {
    $scope.openFilters = function () {
        $rootScope.$broadcast('openFilterMenu');
    };
}

FilterOpenerController.$inject = ['$scope', '$rootScope'];

window.angular.module('icdsApp').component("filterOpener",  {
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('filter-opener.directive');
    }],
    controller: FilterOpenerController,
});
