/* global moment */

window.angular.module('icdsApp').factory('dateHelperService', ['$location', function ($location) {
    function getSelectedMonth() {
        // gets the selected month from $location or defaults to the current month
        // note that this is a 1-indexed month
        return $location.search()['month'] !== void(0) ? parseInt($location.search()['month']) : new Date().getMonth() + 1;
    }
    function getSelectedYear() {
        // gets the selected year from $location or defaults to the current month
        return $location.search()['year'] !== void(0) ? parseInt($location.search()['year']) : new Date().getFullYear();
    }
    function getSelectedDate() {
        // gets the selected date which is the first of the current month, year
        return new Date(getSelectedYear(), getSelectedMonth() - 1, 1);
    }
    function updateSelectedMonth(month, year) {
        $location.search('month', month);
        $location.search('year', year);
    }
    function getSelectedMonthDisplay() {
        var formattedMonth = moment(getSelectedMonth(), 'MM').format('MMMM');
        return formattedMonth + ' ' + getSelectedYear();
    }
    return {
        getSelectedMonth: getSelectedMonth,
        getSelectedYear: getSelectedYear,
        getSelectedDate: getSelectedDate,
        getSelectedMonthDisplay: getSelectedMonthDisplay,
        updateSelectedMonth: updateSelectedMonth,
    };
}]);
