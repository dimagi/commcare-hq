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
        $scope.hasLocation = false;
        $scope.hasDate = false;
        $scope.filterData = {};
        $scope.$broadcast('request_filter_data',{});
    };
    $scope.$on('filter_data', function (event, data) {
        if (data.hasLocation) {
            $scope.hasLocation = true;
            $scope.filterData['location'] = data.location;
            $scope.filterData['locationLevel'] = data.locationLevel;
        } else if (data.hasDate) {
            $scope.hasDate = true;
            $scope.filterData['date'] = data.date;
            $scope.filterData['month'] = data.month;
            $scope.filterData['year'] = data.year;
        }
        if ($scope.hasLocation && $scope.hasDate) {
            // if we have all the data then pass it along to other places
            $scope.$emit('mobile_filter_data_changed', $scope.filterData);
        }
    });
}


MobileFiltersController.$inject = ['$scope'];

window.angular.module('icdsApp').directive("mobileFilters", ['templateProviderService', function (templateProviderService) {
    return {
        restrict:'E',
        scope: {
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
