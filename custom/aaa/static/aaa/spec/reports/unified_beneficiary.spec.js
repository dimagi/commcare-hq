describe('Unified Beneficiary', function () {

    var unifiedBeneficiaryModel;

    beforeEach(function () {
        unifiedBeneficiaryModel = hqImport('aaa/js/reports/unified_beneficiary').unifiedBeneficiary();
    });

    it('test check title', function () {
        assert.equal(unifiedBeneficiaryModel.title, 'Unified Beneficiary');
    });

    it('test check slug', function () {
        assert.equal(unifiedBeneficiaryModel.slug, 'unified_beneficiary');
    });

    it('test filters', function () {
        assert.isTrue(unifiedBeneficiaryModel.hasOwnProperty('filters'));
        assert.equal(3, Object.keys(unifiedBeneficiaryModel.filters).length);
        assert.isTrue(unifiedBeneficiaryModel.filters.hasOwnProperty('month-year-filter'));
        assert.isTrue(unifiedBeneficiaryModel.filters.hasOwnProperty('location-filter'));
        assert.isTrue(unifiedBeneficiaryModel.filters.hasOwnProperty('beneficiary-type-filter'));
    });

    it('test possible views', function () {
        assert.isTrue(unifiedBeneficiaryModel.hasOwnProperty('views'));
        assert.equal(3, Object.keys(unifiedBeneficiaryModel.views).length);
        assert.isTrue(unifiedBeneficiaryModel.views.hasOwnProperty('eligible_couple'));
        assert.isTrue(unifiedBeneficiaryModel.views.hasOwnProperty('pregnant_women'));
        assert.isTrue(unifiedBeneficiaryModel.views.hasOwnProperty('child'));
    });
});
