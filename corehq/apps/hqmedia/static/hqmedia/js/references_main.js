/* globals MultimediaReferenceController */
hqDefine("hqmedia/js/references_main", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
            $loading = $(".hq-loading");
        $.ajax({
            url: initialPageData.reverse('hqmedia_references'),
            data: { json: 1 },
            success: function (data) {
                $loading.remove();
                var referenceController = hqImport('hqmedia/js/hqmedia.reference_controller').MultimediaReferenceController({
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
