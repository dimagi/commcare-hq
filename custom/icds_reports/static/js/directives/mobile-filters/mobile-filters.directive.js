function MobileFiltersController($scope, $rootScope) {
    const MONTH = 'month';
    const LOCATION = 'location';
    $scope.selectedTab = LOCATION;
    if ($scope.$ctrl && $scope.$ctrl.selectSddDate) {
        $scope.selectedTab = MONTH;
    }
    $scope.filterData = {};
    var vm = this;
    vm.showGenderFilter = false;
    vm.showAgeFilter = false;
    // eg:vm.filters = ['gender', 'age']
    // this array has filters that are not to be shown. so if 'gender' is not in array, it can be shown.
    if (vm.filters && vm.filters.indexOf('gender') === -1) {
        vm.showGenderFilter = true;
    }
    if (vm.filters && vm.filters.indexOf('age') === -1) {
        vm.showAgeFilter = true;
    }
    $scope.closeFilters = function () {
        $rootScope.$broadcast('closeFilterMenu', {});
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
        // if neither of the filters exist, we consider filter data is received. else we wait till data is received to
        // emit 'mobile_filter_data_changed' event.
        $scope.receivedAdditionalFilterData = !(vm.showAgeFilter || vm.showGenderFilter);
        $scope.filterData = {};
        $scope.$broadcast('request_filter_data',{});
    };
    $scope.resetFilters = function () {
        $scope.$broadcast('reset_filter_data',{});
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
        } else if (data.hasAdditionalFilterData) {
            $scope.filterData['gender'] = data.gender;
            $scope.filterData['age'] = data.age;
            $scope.receivedAdditionalFilterData = true;
        }
        if ($scope.hasLocation && $scope.hasDate && $scope.receivedAdditionalFilterData ) {
            // if we have all the data then pass it along to other places
            $rootScope.$broadcast('mobile_filter_data_changed', $scope.filterData);
        }
    });
}


MobileFiltersController.$inject = ['$scope', '$rootScope'];

window.angular.module('icdsApp').component("mobileFilters", {
    bindings: {
        selectedLocations: '<',
        selectAwc: '<?',
        filters: '<',
        selectSddDate: '<?',
    },
    templateUrl: ['templateProviderService', function (templateProviderService) {
        return templateProviderService.getTemplate('mobile-filters.directive');
    }],
    controller: MobileFiltersController,
    controllerAs: "$ctrl",
});
