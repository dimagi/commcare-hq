describe('Unified Beneficiary Details', function () {

    var unifiedBeneficiaryDetails, pageData;

    beforeEach(function () {
        pageData = hqImport('hqwebapp/js/initial_page_data');
        pageData.registerUrl('unified_beneficiary_details', 'unified_beneficiary_details/details_type/beneficiary_id/');
        unifiedBeneficiaryDetails = hqImport('aaa/js/reports/unified_beneficiary_details').unifiedBeneficiaryDetails();
    });

    it('test check title', function () {
        assert.equal(unifiedBeneficiaryDetails.title, 'Unified Beneficiary Details');
    });

    it('test check slug', function () {
        assert.equal(unifiedBeneficiaryDetails.slug, 'unified_beneficiary_details');
    });

    it('test possible details types', function () {
        assert.isTrue(unifiedBeneficiaryDetails.hasOwnProperty('detailsTypes'));
        assert.equal(3, Object.keys(unifiedBeneficiaryDetails.detailsTypes).length);
        assert.isTrue(unifiedBeneficiaryDetails.detailsTypes.hasOwnProperty('child'));
        assert.isTrue(unifiedBeneficiaryDetails.detailsTypes.hasOwnProperty('pregnant_women'));
        assert.isTrue(unifiedBeneficiaryDetails.detailsTypes.hasOwnProperty('eligible_couple'));
    });
});
