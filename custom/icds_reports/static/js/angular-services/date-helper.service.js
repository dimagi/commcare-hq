/* global moment */

window.angular.module('icdsApp').factory('dateHelperService', ['$location', function ($location) {
    var reportStartDates = {
        'sdd': new Date(2019, 1),
    };

    var defaultStartYear = 2017;
    var defaultStartMonth = 3;

    function getValidSelectedDate() {
        var selectedMonth = parseInt($location.search()['month']) || new Date().getMonth() + 1;
        var selectedYear =  parseInt($location.search()['year']) || new Date().getFullYear();
        var currentDate = new Date();

        var selectedDate = new Date(selectedYear, selectedMonth - 1, currentDate.getDate());

        selectedDate = checkAndGetValidDate(selectedDate);
        $location.search()['month'] ? $location.search('month', selectedDate.getMonth() + 1) : void(0);
        $location.search()['year'] ? $location.search('year', selectedDate.getFullYear()) : void(0);
        return selectedDate;
    }
    function getSelectedMonth() {
        // gets the selected month from $location or defaults to the current month if it is already 3rd of the month
        // or above. else defaults to previous month
        // note that this is a 1-indexed month
        return (getValidSelectedDate().getMonth() + 1);
    }
    function getSelectedYear() {
        // gets the selected year from $location or defaults to the current year if the date is more than jan 2nd
        // else defaults to previous year
        return getValidSelectedDate().getFullYear();
    }
    function getSelectedDate() {
        // gets the selected date which is the first of the selected month, year
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
    function getCustomAvailableMonthsForReports(selectedYear, selectedMonth, monthsCopy, isSDD) {
        var months = monthsCopy;

        if (selectedYear === new Date().getFullYear()) {
            // this variable is used to decide if current month should be added to months list of the current year
            var addCurrentMonth = !isBetweenFirstAndThirdDayOfCurrentMonth(new Date());
            var maxMonthInCurrentYear = addCurrentMonth ? (new Date().getMonth() + 1) : (new Date().getMonth());
            months = _.filter(monthsCopy, function (month) {
                if (addCurrentMonth) {
                    return month.id <= new Date().getMonth() + 1;
                } else {
                    return month.id <= new Date().getMonth();
                }
            });
            selectedMonth = selectedMonth <= maxMonthInCurrentYear ? selectedMonth : maxMonthInCurrentYear;

        } else {

            // Checks if its Service delivery dashboard and the selected year is 2019 then its month list
            // should start from Feb
            if (isSDD && selectedYear === reportStartDates['sdd'].getFullYear()) {
                months = _.filter(monthsCopy, function (month) {
                    return month.id >= reportStartDates['sdd'].getMonth() + 1;
                });

                selectedMonth = selectedMonth >= reportStartDates['sdd'].getMonth() + 1 ?
                    selectedMonth : reportStartDates['sdd'].getMonth() + 1;
            }

            // Dashboard data is available from 2017 March
            if (selectedYear === 2017) {
                months = _.filter(monthsCopy, function (month) {
                    return month.id >= 3;
                });
                selectedMonth = selectedMonth >= 3 ? selectedMonth : 3;
            }

        }
        return {
            'months': months,
            'selectedMonth': selectedMonth,
        };

    }
    function getStartingMonth(isSDD) {
        if (isSDD) {
            return reportStartDates['sdd'].getMonth() + 1;
        }
        return defaultStartMonth;
    }
    function getStartingYear(isSDD) {
        if (isSDD) {
            return reportStartDates['sdd'].getFullYear();
        }
        return defaultStartYear;
    }
    function getReportStartDates() {
        return reportStartDates;
    }
    function isBetweenFirstAndThirdDayOfCurrentMonth(date) {
        var currentDate = new Date();
        return (date < new Date(currentDate.getFullYear(), currentDate.getMonth(), 3)) &&
            (date >= new Date(currentDate.getFullYear(), currentDate.getMonth(), 1));
    }
    function checkAndGetValidDate(date) {
        var currentDate = new Date();
        if (isBetweenFirstAndThirdDayOfCurrentMonth(date)) {
            return new Date(currentDate.getFullYear(), (currentDate.getMonth() - 1));
        }
        return date;
    }
    return {
        getSelectedMonth: getSelectedMonth,
        getSelectedYear: getSelectedYear,
        getSelectedDate: getSelectedDate,
        getSelectedMonthDisplay: getSelectedMonthDisplay,
        updateSelectedMonth: updateSelectedMonth,
        getCustomAvailableMonthsForReports: getCustomAvailableMonthsForReports,
        getStartingYear: getStartingYear,
        getStartingMonth: getStartingMonth,
        getReportStartDates: getReportStartDates,
        getValidSelectedDate: getValidSelectedDate,
        checkAndGetValidDate: checkAndGetValidDate,
    };
}]);
