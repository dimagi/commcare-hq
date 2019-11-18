hqDefine("aaa/js/reports/program_overview", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'aaa/js/utils/reach_utils',
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
        self.value = options.value;
        self.total = options.total || 0;
        self.pastMonthValue = options.past_month_value || 0;

        self.isNumeric = function () {
            return self.format === 'numeric';
        };

        self.isPercent = function () {
            return self.format === 'percent';
        };

        self.percentFormat = function () {
            var value = self.value * 100 / (self.total || 1);
            return value.toFixed(2) + " %";
        };

        self.diffBetweenMonths = function () {
            var diff = ((self.value - self.pastMonthValue) * 100) / (self.pastMonthValue || 1);
            if (diff > 0) {
                return '(+' + diff.toFixed(2) + '% from last month)';
            } else {
                return '(' + diff.toFixed(2) + '% from last month)';
            }

        };
        return self;
    };

    var programOverviewModel = function () {
        var self = {};
        self.sections = ko.observableArray();
        self.title = 'Program Overview';
        self.slug = 'program_overview';
        self.postData = reachUtils.postData({});
        self.localStorage = reachUtils.localStorage();
        self.reachUtils = reachUtils.reachUtils();
        self.filters = {
            'month-year-filter': {},
            'location-filter': {},
        };

        self.updateSections = function (data) {
            self.sections([]);
            _.each(data.data, function (element) {
                var section = [];
                element.forEach(function (indicator) {
                    section.push(indicatorModel(indicator));
                });
                self.sections.push(section);
            });
        };

        self.callback = function () {
            $.post(initialPageData.reverse('program_overview_api'), self.postData, function (data) {
                self.updateSections(data);
            });
        };

        self.isActive = function (slug) {
            return self.slug === slug;
        };

        return self;
    };

    $(function () {
        var model = programOverviewModel();
        if ($('#aaa-dashboard')[0] !== void(0)) {
            $('#aaa-dashboard').koApplyBindings(model);
            model.callback();
        }
    });

    return {
        programOverviewModel: programOverviewModel,
    };
});
