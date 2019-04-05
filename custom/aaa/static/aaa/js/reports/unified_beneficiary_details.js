hqDefine("aaa/js/reports/unified_beneficiary_details", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'aaa/js/utils/reach_utils',
    'aaa/js/models/eligible_couple',
    'aaa/js/models/child',
    'aaa/js/models/pregnant_women',
], function (
    $,
    ko,
    _,
    initialPageData,
    reachUtils,
    eligibleCoupleModel,
    childUtils,
    pregnantWomenModel
) {

    var unifiedBeneficiaryDetails = function () {
        var self = {};
        self.title = 'Unified Beneficiary Details';
        self.slug = 'unified_beneficiary_details';

        self.selectedType = initialPageData.get('selected_type');
        self.postData = reachUtils.postData({
            selectedMonth: initialPageData.get('selected_month'),
            selectedYear: initialPageData.get('selected_year'),
        });
        self.reachUtils = reachUtils.reachUtils();
        self.localStorage = reachUtils.localStorage();

        self.locationDetails = initialPageData.get('beneficiary_location_names');

        self.detailsTypes = {
            child: childUtils.detailsView(self.postData),
            pregnant_women: pregnantWomenModel.detailsView(self.postData),
            eligible_couple: eligibleCoupleModel.detailsView(self.postData),
        };

        self.detailsModel = self.detailsTypes[self.selectedType];

        self.showSection = function (section) {
            return self.detailsModel.sections.indexOf(section) !== -1;
        };

        self.callback = function () {
            self.detailsModel.callback();
        };

        self.isActive = function (slug) {
            return self.slug === slug;
        };

        return self;
    };

    $(function () {
        var model = unifiedBeneficiaryDetails();
        $('#aaa-dashboard').koApplyBindings(model);
        model.callback();
    });

    return {
        unifiedBeneficiaryDetails: unifiedBeneficiaryDetails,
    };
});
