/* global _ */

var url = hqImport('hqwebapp/js/urllib.js').reverse;

function ProgressReportController($scope, $location, progressReportService, storageService) {
    var vm = this;
    $location.search(storageService.get());
    vm.filtersData = $location.search();
    vm.filters = ['gender', 'age'];
    vm.label = "Progress Report";
    vm.data = {};
    vm.dates = [];
    vm.now = new Date().getMonth() + 1;
    vm.showWarning = storageService.getKey('month') === void(0) || vm.now === storageService.getKey('month');

    $scope.$on('filtersChange', function() {
        vm.showWarning =  vm.now === storageService.getKey('month');
        vm.loadData();
    });

    vm.loadData = function () {
        progressReportService.getData(vm.filtersData).then(function(response) {
            vm.data = response.data.config;
        });
    };

    vm.sumValues = function(values) {
        var sum = _.reduce(values, function(memo, num) { return memo + num; }, 0);
        return sum / values.length;
    };

    vm.checkColor = function(color, index, data) {
        if (color === 'black') {
            return index === 1 || (index > 0 && data[index]['html'] === data[index - 1]['html']);
        } else if (color ==='red') {
            return index > 0 && data[index]['html'] < data[index - 1]['html'];
        } else if (color === 'green') {
            return  index > 0 && data[index]['html'] > data[index - 1]['html'];
        } else {
            return false;
        }
    }

    vm.loadData();
}

ProgressReportController.$inject = ['$scope', '$location', 'progressReportService', 'storageService'];

window.angular.module('icdsApp').directive('progressReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'progress-report.directive'),
        bindToController: true,
        controller: ProgressReportController,
        controllerAs: '$ctrl',
    };
});
