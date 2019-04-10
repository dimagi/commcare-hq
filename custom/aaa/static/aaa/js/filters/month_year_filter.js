hqDefine('aaa/js/filters/month_year_filter', [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment',
], function (
    $,
    ko,
    _,
    moment
) {
    return {
        viewModel: function (params) {
            var self = {};
            self.slug = 'month-year-filter';
            self.availableYears = ko.observableArray();
            self.availableMonths = ko.observableArray();
            self.selectedMonth =  ko.observable(params.postData.selectedMonth());
            self.selectedYear = ko.observable(params.postData.selectedYear());

            var availableMonthsCopy = [];
            moment.months().forEach(function (key, value) {
                availableMonthsCopy.push({
                    name: key,
                    id: value + 1,
                });
            });

            var updateMonths = function (selectedYear) {
                if (selectedYear === moment().year()) {
                    self.availableMonths(_.filter(availableMonthsCopy, function (month) {
                        return month.id <= moment().month() + 1;
                    }));
                    self.selectedMonth(self.selectedMonth() <= moment().month() + 1 ? self.selectedMonth() : moment().month() + 1);
                } else {
                    self.availableMonths(availableMonthsCopy);
                }
            };

            updateMonths(self.selectedYear());

            for (var year = 2019; year <= moment().year(); year++) {
                self.availableYears.push({
                    name: year,
                    id: year,
                });
            }

            self.selectedYear.subscribe(function (newValue) {
                updateMonths(newValue);
            });

            params.filters[self.slug].applyFilter = function () {
                params.postData.selectedYear(self.selectedYear());
                params.postData.selectedMonth(self.selectedMonth());
            };

            params.filters[self.slug].verify = function () {
                return true;
            };

            params.filters[self.slug].resetFilters = function () {
                self.selectedMonth(moment().month() + 1);
                self.selectedYear(moment().year());
            };

            return self;
        },
        template: '<div data-bind="template: { name: \'month-year-template\' }"></div>',
    };
});
