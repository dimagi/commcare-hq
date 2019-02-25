/* global moment, sinon */

describe('Reach Month Year Filter', function () {
    var monthYearModel, reachUtils, clock;

    beforeEach(function () {
        monthYearModel = hqImport('aaa/js/filters/month_year_filter');
        reachUtils = hqImport('aaa/js/utils/reach_utils');
        var today = moment('2020-01-01').toDate();
        clock = sinon.useFakeTimers(today.getTime());
    });

    afterEach(function () {
        clock.restore();
    });

    it('test template', function () {
        assert.equal(monthYearModel.template, '<div data-bind="template: { name: \'month-year-template\' }"></div>');
    });

    it('test month year model initialization', function () {
        var params = {
            postData: reachUtils.postData({}),
            callback: function () {},
            filters: {'month-year-filter': {}},
        };
        var model = monthYearModel.viewModel(params);

        var expectedYears = [
            {id: 2019, name: 2019},
            {id: 2020, name: 2020},
        ];
        _.each(expectedYears, function (year, idx) {
            assert.equal(model.availableYears()[idx].id, year.id);
            assert.equal(model.availableYears()[idx].name, year.name);
        });

        // only one month because now is set to the '2020-01-01'
        var expectedMonths = [
            {id: 1, name: "January"},
        ];

        assert.equal(model.availableMonths().length, 1);
        _.each(expectedMonths, function (year, idx) {
            assert.equal(model.availableMonths()[idx].id, year.id);
            assert.equal(model.availableMonths()[idx].name, year.name);
        });

        assert.equal(model.selectedMonth(), 1);
        assert.equal(model.selectedYear(), 2020);
    });

    it('test month year selected year subscribe method', function () {
        var params = {
            postData: reachUtils.postData({}),
            callback: function () {},
            filters: {'month-year-filter': {}},
        };
        var model = monthYearModel.viewModel(params);

        var expectedYears = [
            {id: 2019, name: 2019},
            {id: 2020, name: 2020},
        ];
        _.each(expectedYears, function (year, idx) {
            assert.equal(model.availableYears()[idx].id, year.id);
            assert.equal(model.availableYears()[idx].name, year.name);
        });

        // only one month because now is set to the '2020-01-01'
        var expectedMonths = [
            {id: 1, name: "January"},
        ];

        assert.equal(model.availableMonths().length, 1);
        _.each(expectedMonths, function (year, idx) {
            assert.equal(model.availableMonths()[idx].id, year.id);
            assert.equal(model.availableMonths()[idx].name, year.name);
        });

        assert.equal(model.selectedMonth(), 1);
        assert.equal(model.selectedYear(), 2020);

        model.selectedYear(2019);

        assert.equal(model.selectedMonth(), 1);
        assert.equal(model.selectedYear(), 2019);

        expectedYears = [
            {id: 2019, name: 2019},
            {id: 2020, name: 2020},
        ];
        _.each(expectedYears, function (year, idx) {
            assert.equal(model.availableYears()[idx].id, year.id);
            assert.equal(model.availableYears()[idx].name, year.name);
        });

        expectedMonths = [
            {id: 1, name: "January"},
            {id: 2, name: "February"},
            {id: 3, name: "March"},
            {id: 4, name: "April"},
            {id: 5, name: "May"},
            {id: 6, name: "June"},
            {id: 7, name: "July"},
            {id: 8, name: "August"},
            {id: 9, name: "September"},
            {id: 10, name: "October"},
            {id: 11, name: "November"},
            {id: 12, name: "December"},
        ];

        assert.equal(model.availableMonths().length, 12);
        _.each(expectedMonths, function (year, idx) {
            assert.equal(model.availableMonths()[idx].id, year.id);
            assert.equal(model.availableMonths()[idx].name, year.name);
        });
    });
});
