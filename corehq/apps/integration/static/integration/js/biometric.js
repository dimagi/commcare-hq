hqDefine('integration/js/biometric', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'integration/js/simprints',
    'commcarehq',
], function (
    $,
    initialPageData,
    simprints
) {
    $(function () {
        var simprintsModel = simprints.simprintsFormModel(initialPageData.get('simprintsFormData'));
        $('#simprints-form').koApplyBindings(simprintsModel);
    });
});
