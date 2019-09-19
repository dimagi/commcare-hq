hqDefine("hqmedia/js/references_main", function () {
    // TODO: pull MultimediaReferenceController model in here? And rename the other file.

    $(function () {
        var referenceController = hqImport('hqmedia/js/reference_controller').MultimediaReferenceController();
        $("#multimedia-reference-checker").koApplyBindings(referenceController);
    });
});
