hqDefine("app_manager/js/details/case_detail_print", [
    "hqwebapp/js/initial_page_data",
    "hqmedia/js/uploaders",
    "hqmedia/js/media_reference_models",
], function (
    initialPageData,
    uploaders,
    mediaReferenceModels,
) {
    var printRef, printTemplateUploader;
    const printUploader = initialPageData.get("print_uploader_js");
    if (printUploader) {
        printTemplateUploader = uploaders.uploader(
            printUploader.slug,
            printUploader.options,
        );
        printRef = mediaReferenceModels.BaseMediaReference(initialPageData.get('print_ref'));
        printRef.upload_controller = printTemplateUploader;
        printRef.setObjReference(initialPageData.get('print_media_info'));
        printTemplateUploader.currentReference = printRef;
    }

    return {
        getPrintRef: function () {
            return printRef;
        },
        getPrintTemplateUploader: function () {
            return printTemplateUploader;
        },
    };
});
