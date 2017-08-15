/* global _ */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function ProgressReportController($scope, $location, progressReportService, storageService, userLocationId) {
    var vm = this;
    if (Object.keys($location.search()).length === 0) {
        $location.search(storageService.getKey('search'));
    } else {
        storageService.setKey('search', $location.search());
    }
    vm.filtersData = $location.search();
    vm.filters = ['gender', 'age'];
    vm.label = "ICDS-CAS Fact Sheet";
    vm.data = {};
    vm.dates = [];
    vm.now = new Date().getMonth() + 1;
    vm.showWarning = storageService.getKey('search') === void(0) && (storageService.getKey('search')['month'] === void(0) || vm.now === storageService.getKey('search')['month']);

    $scope.$on('filtersChange', function() {
        vm.showWarning =  vm.now === storageService.getKey('search')['month'];
        vm.loadData();
    });

    vm.loadData = function () {
        vm.myPromise = progressReportService.getData(vm.filtersData).then(function(response) {
            vm.data = response.data.config;
        });
    };

    vm.sumValues = function(values) {
        var sum = _.reduce(values, function(memo, num) { return memo + num; }, 0);
        return sum / values.length;
    };

    vm.checkColor = function(color, index, data, reverseColors) {
        if (color === 'black') {
            return index === 1 || (index > 0 && data[index]['html'] === data[index - 1]['html']);
        }
        if (reverseColors === 'true') {
            color = color === 'green' ? 'red': 'green';
        }

        if (color ==='red') {
            return index > 0 && data[index]['html'] < data[index - 1]['html'];
        } else if (color === 'green') {
            return  index > 0 && data[index]['html'] > data[index - 1]['html'];
        } else {
            return false;
        }
    };

    vm.getDisableIndex = function () {
        var i = -1;
        window.angular.forEach(vm.selectedLocations, function (key, value) {
            if (key.location_id === userLocationId) {
                i = value;
            }
        });
        return i;
    };


    vm.moveToLocation = function(loc, index) {
        if (loc === 'national') {
            $location.search('location_id', '');
            $location.search('selectedLocationLevel', -1);
            $location.search('location_name', '');
        } else {
            $location.search('location_id', loc.location_id);
            $location.search('selectedLocationLevel', index);
            $location.search('location_name', loc.name);
        }
    };

    vm.loadData();
}

ProgressReportController.$inject = ['$scope', '$location', 'progressReportService', 'storageService', 'userLocationId'];

window.angular.module('icdsApp').directive('progressReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'progress-report.directive'),
        bindToController: true,
        controller: ProgressReportController,
        controllerAs: '$ctrl',
    };
});
