/* global _ */

var url = hqImport('hqwebapp/js/urllib.js').reverse;

function ProgressReportController($scope, $location, progressReportService) {
    var vm = this;

    vm.filtersData = window.angular.copy($location.search());
    vm.filters = ['gender', 'age'];
    vm.label = "Progress Report";
    vm.data = {};
    vm.dates = [];

    $scope.$on('filtersChange', function() {
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
}

ProgressReportController.$inject = ['$scope', '$location', 'progressReportService'];

window.angular.module('icdsApp').directive('progressReport', function() {
    return {
        restrict: 'E',
        templateUrl: url('icds-ng-template', 'progress-report.directive'),
        bindToController: true,
        controller: ProgressReportController,
        controllerAs: '$ctrl',
    };
});
