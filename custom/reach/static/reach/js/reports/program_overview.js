hqDefine("reach/js/reports/program_overview", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'reach/js/utils/reach_utils',
], function (
    $,
    ko,
    _,
    initialPageData,
    reachUtils
) {
    var indicatorModel = function (options) {
        var self = {};

        self.reachUtils = reachUtils.reachUtils();
        self.indicator = options.indicator;
        self.color = options.color;
        self.format = options.format;
        self.numerator = options.numerator;
        self.denominator = options.denominator || 1;
        self.pastMonthNumerator = options.past_month_numerator || 0;
        self.pastMonthDenominator = options.past_month_denominator || 0;

        self.isNumeric = function () {
            return self.format === 'numeric';
        };

        self.isPercent = function () {
            return self.format === 'percent';
        };

        self.percentFormat = function () {
            var value = self.numerator * 100 / (self.denominator || 1);
            return value.toFixed(2) + " %";
        };

        self.diffBetweenMonths = function () {
            var thisMonth = self.numerator * 100 / (self.denominator || 1);
            var prevMonth = self.pastMonthNumerator * 100 / (self.pastMonthDenominator || 1);

            var diff = ((thisMonth - prevMonth) * 100) / (prevMonth || 1);
            if (diff > 0) {
                return '(+' + diff.toFixed(2) + '% from last month)';
            } else {
                return '(' + diff.toFixed(2) + '% from last month)';
            }

        };
        return self;
    };

    var programOverviewModel = function (options) {
        var self = {};
        self.sections = ko.observableArray();
        self.title = 'Program Overview';
        self.slug = 'program_overview';
        self.postData = reachUtils.postData({});

        self.updateSections = function (data) {
            self.sections([]);
            _.each(data.data, function (element) {
                var section = [];
                element.forEach(function (indicator) {
                    section.push(indicatorModel(indicator));
                });
                self.sections.push(section);
            })
        };

        self.callback = function () {
            $.post(initialPageData.reverse('program_overview_api'), self.postData, function (data) {
                self.updateSections(data);
            })
        };

        self.isActive = function (slug) {
            return self.slug === slug;
        };

        return self;
    };

    return {
        programOverviewModel: programOverviewModel,
    };
});
