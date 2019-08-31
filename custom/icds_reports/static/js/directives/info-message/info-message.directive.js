/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfoMessageController($location) {
    var vm = this;
    vm.previousToPreviousMonth = null;
    vm.previousMonth = null;
    vm.currentMonth = null;
    vm.nextMonth = null;
    vm.year = null;

    vm.showInfoMessage = function () {
        var start = parseInt(vm.start || '1');
        var end = parseInt(vm.end || '2');
        vm.type = vm.type || 'default';

        var selectedMonth = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selectedYear = parseInt($location.search()['year']) || new Date().getFullYear();
        var currentMonth = new Date().getMonth() + 1;
        var currentYear = new Date().getFullYear();
        var currentDate = new Date().getDate();

        if (selectedMonth === currentMonth && selectedYear === currentYear && (currentDate >= start && currentDate <= end)) {
            vm.previousMonth = moment().startOf('month').subtract(1, 'months').format('MMMM');
            vm.previousToPreviousMonth = moment().startOf('month').subtract(2, 'months').format('MMMM');
            vm.currentMonth = moment().format("MMMM");
            vm.nextMonth = moment().startOf('month').add(1, 'months').format("MMMM");
            vm.year = moment().format('YYYY');

            return true;
        }

        return false;
    };
}

InfoMessageController.$inject = ['$location'];

window.angular.module('icdsApp').directive("infoMessage", function () {
    return {
        restrict: 'E',
        scope: {
            type: '@',
            start: '@',
            end: '@'
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'info-message.directive'),
        controller: InfoMessageController,
        controllerAs: "$ctrl",
    };
});
