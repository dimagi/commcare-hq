/* global moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function InfoMessageController($location) {
    var vm = this;
    vm.currentMonth = null;
    vm.lastDayOfPreviousMonth = null;

    vm.showInfoMessage = function () {
        var selectedMonth = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selectedYear = parseInt($location.search()['year']) || new Date().getFullYear();
        var currentMonth = new Date().getMonth() + 1;
        var currentYear = new Date().getFullYear();
        if (!$location.path().startsWith("/fact_sheets") && !$location.path().startsWith("/download") &&
            selectedMonth === currentMonth && selectedYear === currentYear &&
            (new Date().getDate() === 1 || new Date().getDate() === 2)) {
            vm.lastDayOfPreviousMonth = moment().set('date', 1).subtract(1, 'days').format('Do MMMM, YYYY');
            vm.currentMonth = moment().format("MMMM");
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
            data: '=',
        },
        bindToController: true,
        templateUrl: url('icds-ng-template', 'info-message.directive'),
        controller: InfoMessageController,
        controllerAs: "$ctrl",
    };
});
