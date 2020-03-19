/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfoMessageController($location) {
    var vm = this;
    vm.twoMonthsBackMonth = null;
    vm.previousMonth = null;
    vm.yearOfPreviousMonth = null;
    vm.yearOfTwoMonthsAgo = null;
    vm.currentMonth = null;
    vm.nextMonth = null;
    vm.yearOfNextMonth = null;
    vm.year = null;

    vm.getMonthFromDate = function (date) {
        return moment().month(date.getMonth()).format('MMMM');
    };

    vm.getYearFromDate = function (date) {
        return moment().month(date.getMonth()).year(date.getFullYear()).format('YYYY');
    };


    vm.showInfoMessage = function () {
        var start = parseInt(vm.start || '1');
        var end = parseInt(vm.end || '2');
        vm.type = vm.type || 'default';

        var selectedMonth = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selectedYear = parseInt($location.search()['year']) || new Date().getFullYear();
        var now = new Date();
        var currentMonth = now.getMonth() + 1;
        var currentYear = now.getFullYear();
        var currentDate = now.getDate();

        var displayInfoMessage = selectedMonth === currentMonth && selectedYear === currentYear && (currentDate >= start && currentDate <= end);

        if (displayInfoMessage && !$location.path().startsWith("/download")) {
            vm.currentMonth = moment().format("MMMM");
            vm.year = moment().format('YYYY');

            var previousMonthDate = new Date();
            var twoMonthsBackDate = new Date();
            var nextMonthDate = new Date();

            previousMonthDate.setMonth(now.getMonth() - 1);
            twoMonthsBackDate.setMonth(now.getMonth() - 2);
            nextMonthDate.setMonth(now.getMonth() + 1);

            vm.previousMonth = vm.getMonthFromDate(previousMonthDate);
            vm.yearOfPreviousMonth = vm.getYearFromDate(previousMonthDate);


            vm.nextMonth = vm.getMonthFromDate(nextMonthDate);
            vm.yearOfNextMonth = vm.getYearFromDate(nextMonthDate);

            vm.twoMonthsBackMonth = vm.getMonthFromDate(twoMonthsBackDate);
            vm.yearOfTwoMonthsAgo = vm.getYearFromDate(twoMonthsBackDate);
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
            end: '@',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'info-message.directive'),
        controller: InfoMessageController,
        controllerAs: "$ctrl",
    };
});
