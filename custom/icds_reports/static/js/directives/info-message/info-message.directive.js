/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfoMessageController($location) {
    var vm = this;
    vm.previousToPreviousMonth = null;
    vm.previousMonth = null;
    vm.previousYear = null;
    vm.previousToPreviousYear = null;
    vm.currentMonth = null;
    vm.nextMonth = null;
    vm.nextYear = null;
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

        var displayInfoMessage = selectedMonth === currentMonth && selectedYear === currentYear && (currentDate >= start && currentDate <= end);

        if (displayInfoMessage && !$location.path().startsWith("/download")) {
            vm.previousMonth = moment().startOf('month').subtract(1, 'months').format('MMMM');
            vm.previousToPreviousMonth = moment().startOf('month').subtract(2, 'months').format('MMMM');
            vm.currentMonth = moment().format("MMMM");
            vm.nextMonth = moment().startOf('month').add(1, 'months').format("MMMM");
            vm.year = moment().format('YYYY');
            if (currentMonth == 1) {
                vm.previousYear = moment().startOf('year').subtract(1, 'years').format('YYYY');
            } else {
                vm.previousYear = vm.year;
            }
            if (currentMonth == 2) {
                vm.previousToPreviousYear = moment().startOf('year').subtract(1, 'years').format('YYYY');
            } else {
                vm.previousToPreviousYear = vm.previousYear;
            }
            if(currentMonth == 12) {
                vm.nextYear = moment().startOf('year').add(1, 'years').format('YYYY')
            }else {
                vm.nextYear = vm.year;
            }

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
