hqDefine("hqmedia/js/references_main",[
    'hqwebapp/js/initial_page_data',
    'hqmedia/js/hqmedia.reference_controller',
    'jquery',
    'bootstrap', // used for the tooltip
    'app_manager/js/download_async_modal',
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
