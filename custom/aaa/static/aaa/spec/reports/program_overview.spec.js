describe('Reach Program Overview', function () {

    var programOverviewModel;
    var data = hqImport('aaa/spec/fixture/program_overview_fixture');

    var verifyIndicator = function (indicator, expectedValues) {
        assert.equal(indicator.indicator, expectedValues.indicator);
        assert.equal(indicator.color, expectedValues.color);
        assert.equal(indicator.format, expectedValues.format);
        assert.equal(indicator.value, expectedValues.value);
        assert.equal(indicator.total, expectedValues.total);
        assert.equal(indicator.pastMonthValue, expectedValues.pastMonthValue);
        assert.equal(indicator.isNumeric(), expectedValues.isNumeric);
        assert.equal(indicator.isPercent(), expectedValues.isPercent);
        if (indicator.isPercent()) {
            assert.equal(indicator.percentFormat(), expectedValues.percentFormat);
            var secondValueFormat = indicator.reachUtils.toIndiaFormat(indicator.value) + ' / ' + indicator.reachUtils.toIndiaFormat(indicator.total);
            assert.equal(secondValueFormat, expectedValues.secondValueFormat);
        } else {
            assert.equal(indicator.reachUtils.toIndiaFormat(indicator.value), expectedValues.indiaFormat);
        }
        assert.equal(indicator.diffBetweenMonths(), expectedValues.diffBetweenMonths);
    };

    beforeEach(function () {
        programOverviewModel = hqImport('aaa/js/reports/program_overview').programOverviewModel();
    });

    it('test check title', function () {
        assert.equal(programOverviewModel.title, 'Program Overview');
    });

    it('test check slug', function () {
        assert.equal(programOverviewModel.slug, 'program_overview');
    });

    it('test update sections', function () {
        assert.equal(programOverviewModel.sections().length, 0);
        programOverviewModel.updateSections(data.indicators);
        assert.equal(programOverviewModel.sections().length, 2);
    });

    it('test number of indicators', function () {
        assert.equal(programOverviewModel.sections().length, 0);
        programOverviewModel.updateSections(data.indicators);
        var indicators = [];
        _.each(programOverviewModel.sections(), function (section) {
            _.each(section, function (indicator) {
                indicators.push(indicator);
            });
        });
        assert.equal(indicators.length, 6);
    });

    it('test verify numbers in indicators', function () {
        var indicators = [];
        programOverviewModel.updateSections(data.indicators);
        _.each(programOverviewModel.sections(), function (section) {
            _.each(section, function (indicator) {
                indicators.push(indicator);
            });
        });
        _.each(indicators, function (indicator, idx) {
            verifyIndicator(indicator, data.expectedValues[idx]);
        });
    });
});
