hqDefine("hqmedia/js/references_main", [
    'hqwebapp/js/initial_page_data',
    'hqmedia/js/hqmedia.reference_controller',
    'jquery',
    'bootstrap', // used for the tooltip
    'app_manager/js/download_async_modal',
], function (intialPageData, mediareferenceController, $) {
    $(function () {
        var initialPageData = intialPageData.get,
            $loading = $(".hq-loading");
        $.ajax({
            url: initialPageData.reverse('hqmedia_references'),
            data: { json: 1 },
            success: function (data) {
                $loading.remove();
                var referenceController = mediareferenceController.MultimediaReferenceController({
                    references: data.references,
                    objectMap: data.object_map,
                    totals: data.totals,
                });
                referenceController.render();
                $("#multimedia-reference-checker").koApplyBindings(referenceController);
                $('.preview-media').tooltip();
            },
            error: function () {
                $loading.removeClass("alert-info");
                $loading.addClass("alert-danger");
                $loading.text(gettext("Error loading, please refresh the page. If this persists, please report an issue."));
            },
        });
    });
});
