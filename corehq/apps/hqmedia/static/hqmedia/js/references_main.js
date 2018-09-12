/* globals MultimediaReferenceController */
hqDefine("hqmedia/js/references_main", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get,
            referenceController = new MultimediaReferenceController(
                initialPageData("references"),
                initialPageData("object_map"),
                initialPageData("totals")
            );
        referenceController.render();
        $("#multimedia-reference-checker").koApplyBindings(referenceController);

        $('.preview-media').tooltip();
    });
});
