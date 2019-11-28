function MobileFiltersController($scope) {
    const MONTH = 'month';
    const LOCATION = 'location';
    $scope.selectedTab = MONTH;
    $scope.filterData = {};
    $scope.closeFilters = function () {
        $scope.$emit('closeFilterMenu', {});
    };
    $scope.selectMonthTab = function () {
        $scope.selectedTab = MONTH;
    };
    $scope.selectLocationTab = function () {
        $scope.selectedTab = LOCATION;
    };
    $scope.applyFilters = function () {
        $scope.$broadcast('request_filter_data',{});
    };
    $scope.$on('filter_data', function (event, data) {
        if (data.hasLocation) {
            $scope.filterData['hasLocation'] = true;
            $scope.filterData['location'] = data.location;
            $scope.filterData['locationLevel'] = data.locationLevel;
        } else {
            // todo: assign filter data from date picker
        }
        // send data to other places
        // todo: only send this after getting both location and month?
        $scope.$emit('mobile_filter_data_changed', $scope.filterData);
    });
}


MobileFiltersController.$inject = ['$scope'];

window.angular.module('icdsApp').directive("mobileFilters", ['templateProviderService', function (templateProviderService) {
    return {
        restrict:'E',
        scope: {
            data: '=',
            filters: '=',
            selectedLocations: '=',
        },
        bindToController: true,
        templateUrl: function () {
            return templateProviderService.getTemplate('mobile-filters.directive');
        },
        controller: MobileFiltersController,
        controllerAs: "$ctrl",
    };
}]);
