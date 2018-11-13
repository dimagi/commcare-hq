/* globals MultimediaReferenceController */
hqDefine("hqmedia/js/references_main",[
    'hqwebapp/js/initial_page_data',
    'hqmedia/js/hqmedia.reference_controller',
    'jquery',
    'bootstrap',
], function (intialPageData, mediareferenceController, $) {
    $(function () {
        var initialPageData = intialPageData.get,
            referenceController = mediareferenceController.MultimediaReferenceController(
                initialPageData("references"),
                initialPageData("object_map"),
                initialPageData("totals")
            );
        referenceController.render();
        $("#multimedia-reference-checker").koApplyBindings(referenceController);

        $('.preview-media').tooltip();
    });
});
