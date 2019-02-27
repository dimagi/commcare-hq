hqDefine("aaa/js/reports/unified_beneficiary", [
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

        var detailsTypes = {
            // child: childUtils.detailsView(),
            // pregnant_women: pregnantWomenModel.detailsView(),
            eligible_couples: eligibleCoupleModel.detailsView(self.postData),
        };

        self.detailsModel = detailsTypes[self.selectedType];

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
