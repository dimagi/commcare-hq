/* globals MultimediaReferenceController */
hqDefine("hqmedia/js/references_main", function () {
    $(function () {
        // TODO: spinner
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        $.ajax({
            url: initialPageData.reverse('hqmedia_references'),
            data: { json: 1 },
            success: function (data) {
                var referenceController = hqImport('hqmedia/js/hqmedia.reference_controller').MultimediaReferenceController({
                    references: data.references,
                    objectMap: data.object_map,
                    totals: data.totals,
                });
                referenceController.render();
                $("#multimedia-reference-checker").koApplyBindings(referenceController);
                $('.preview-media').tooltip();
            },
            // TODO: error
        });
    });
});
