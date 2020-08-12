/* global moment */

window.angular.module('icdsApp').factory('dateHelperService', ['$location', function ($location) {
    var reportStartDates = {
        'sdd': new Date(2019, 1),
        'ppd': new Date(2019, 3),
    };

    var quarterlyDataAvailabilityDates = {
        'year': 2019,
        'quarter': 2,
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
    function getCustomAvailableMonthsForReports(selectedYear, selectedMonth, monthsCopy, isSDD, isPPD) {
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
            } else if (isPPD && selectedYear === reportStartDates['ppd'].getFullYear()) {
                // getting custom months for PPD
                months = _.filter(monthsCopy, function (month) {
                    return month.id >= reportStartDates['ppd'].getMonth() + 1;
                });

                selectedMonth = selectedMonth >= reportStartDates['ppd'].getMonth() + 1 ?
                    selectedMonth : reportStartDates['ppd'].getMonth() + 1;
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
    function getStartingMonth(isSDD, isPPD) {
        if (isSDD) {
            return reportStartDates['sdd'].getMonth() + 1;
        } else if (isPPD) {
            return reportStartDates['ppd'].getMonth() + 1;
        }
        return defaultStartMonth;
    }
    function getStartingYear(isSDD, isPPD) {
        if (isSDD) {
            return reportStartDates['sdd'].getFullYear();
        } else if (isPPD) {
            return reportStartDates['ppd'].getFullYear();
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
    function getLatestQuarterAvailable() {
        // this function returns the latest quarter for which data is available along with the year to which this quarter belongs to.
        // if the year is still in its first quarter, it returns previous year and 4th quarter of last year
        var currentDate = new Date();
        var maxQuarterInCurrentYear = Math.floor(currentDate.getMonth() / 3);
        return {
            'quarter': maxQuarterInCurrentYear ? maxQuarterInCurrentYear : 4,
            'year': maxQuarterInCurrentYear ? currentDate.getFullYear() : (currentDate.getFullYear() - 1),
        };
    }
    function getSelectedQuarterAndYear() {
        // this function handles if data for selected quarter and year is not available
        var latestQuarter = getLatestQuarterAvailable();
        var selectedQuarter = parseInt($location.search()['quarter']) || latestQuarter['quarter'];
        var selectedYear =  parseInt($location.search()['year']) || latestQuarter['year'];

        if (selectedYear > latestQuarter['year']) {
            selectedQuarter = latestQuarter['quarter'];
            selectedYear = latestQuarter['year'];
        } else if (selectedYear < quarterlyDataAvailabilityDates['year']) {
            selectedQuarter = quarterlyDataAvailabilityDates['quarter'];
            selectedYear = quarterlyDataAvailabilityDates['year'];
        } else if ((selectedYear === latestQuarter['year']) && (selectedQuarter > latestQuarter['quarter'])) {
            selectedQuarter = latestQuarter['quarter'];
        } else if ((selectedYear === quarterlyDataAvailabilityDates['year']) &&
            (selectedQuarter < quarterlyDataAvailabilityDates['quarter'])) {
            selectedQuarter = quarterlyDataAvailabilityDates['quarter'];
        }
        $location.search()['quarter'] ? $location.search('quarter', selectedQuarter) : void(0);
        $location.search()['year'] ? $location.search('year', selectedYear) : void(0);
        return {
            'quarter': selectedQuarter,
            'year': selectedYear,
        };
    }
    function getQuarterAndYearFromDate(month, year) {
        // this function is used to get quarter and year while switching from monthly to quarterly data period
        var currentDate = new Date();
        var maxQuarterInCurrentYear = Math.floor(currentDate.getMonth() / 3);

        if (year === currentDate.getFullYear()) {
            if (!maxQuarterInCurrentYear) {
                return {
                    'year': year - 1,
                    'quarter': 4,
                };
            } else {
                if (Math.floor(month / 3) < maxQuarterInCurrentYear) {
                    return {
                        'year': year,
                        'quarter': Math.floor(month / 3) + 1,
                    };
                } else {
                    return {
                        'year': year,
                        'quarter': maxQuarterInCurrentYear,
                    };
                }
            }
        } else {
            return {
                'year': year,
                'quarter': Math.floor(month / 3) + 1,
            };
        }
    }
    function getCustomAvailableQuarters(selectedYear, selectedQuarter, quarters) {
        // displaying available quarters for a selected year
        // for 2019, displaying from 2nd quarter and if current year is selected, displaying till the latest quarter
        // This function never receives an year which is still in its first quarter as parameter. That is handled in
        // the places where this function is called. (restricted showing the year in the date filter if it is still in
        // its first quarter)
        var quartersCopy = window.angular.copy(quarters);
        var currentDate = new Date();
        var maxQuarterInCurrentYear = Math.floor(currentDate.getMonth() / 3);
        if (selectedYear === currentDate.getFullYear()) {
            selectedQuarter = (selectedQuarter <= maxQuarterInCurrentYear) ? selectedQuarter : maxQuarterInCurrentYear;
            return {
                'selectedQuarter': selectedQuarter,
                'quarters': quartersCopy.slice(0, maxQuarterInCurrentYear),
            };
        } else if (selectedYear === 2019) {
            selectedQuarter = (selectedQuarter > 1) ? selectedQuarter : 2;
            return {
                'selectedQuarter': selectedQuarter,
                'quarters': quartersCopy.slice(1),
            };
        }
        return {
            'selectedQuarter': selectedQuarter,
            'quarters': quartersCopy,
        };
    }
    function updateSelectedQuarter(quarter, year) {
        $location.search('quarter', quarter);
        $location.search('year', year);
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
        getQuarterAndYearFromDate: getQuarterAndYearFromDate,
        getLatestQuarterAvailable: getLatestQuarterAvailable,
        getCustomAvailableQuarters: getCustomAvailableQuarters,
        getSelectedQuarterAndYear: getSelectedQuarterAndYear,
        updateSelectedQuarter: updateSelectedQuarter,
    };
}]);
