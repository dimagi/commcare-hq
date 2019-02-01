hqDefine('reach/js/filters/month_year_filter', [
    'jquery',
    'knockout',
    'underscore',
    'moment/moment'
], function (
    $,
    ko,
    _,
    moment,
) {
    return {
        viewModel: function (params) {
            var self = {};
            self.showFilter = ko.observable(false);
            self.availableYears = ko.observableArray();
            self.availableMonths = ko.observableArray();
            self.selectedMonth =  ko.observable(params.postData.selectedMonth);
            self.selectedYear = ko.observable(params.postData.selectedYear);

            var availableMonthsCopy = [];
            moment.months().forEach(function(key, value) {
                availableMonthsCopy.push({
                    name: key,
                    id: value + 1,
                });
            });

            var updateMonths = function (selectedYear) {
                if (selectedYear === moment().year()) {
                    self.availableMonths(_.filter(availableMonthsCopy, function(month) {
                        return month.id <= moment().month() + 1;
                    }));
                    self.selectedMonth(self.selectedMonth() <= moment().month() + 1 ? self.selectedMonth() : moment().month() + 1);
                } else {
                    self.availableMonths(availableMonthsCopy);
                }
            };

            updateMonths(self.selectedYear());

            for (var year=2017; year <= moment().year(); year++ ) {
                self.availableYears.push({
                    name: year,
                    id: year,
                });
            }

            self.resetFilter = function () {
                self.selectedMonth(moment().month() + 1);
                self.selectedYear(moment().year())
            };

            self.selectedYear.subscribe(function(newValue) {
                updateMonths(newValue);
            });

            self.applyFilters = function() {
                params.postData.selectedMonth = self.selectedMonth();
                params.postData.selectedYear = self.selectedYear();
                self.showFilter(false);
                params.callback()
            };
            return self
        },
        template: '<div data-bind="template: { name: \'month-year-template\' }"></div>',
    };
});
