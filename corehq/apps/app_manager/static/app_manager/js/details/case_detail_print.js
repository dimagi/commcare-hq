"use strict";
hqDefine("app_manager/js/details/case_detail_print", function () {
    var printRef, printTemplateUploader;
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        printUploader = initialPageData.get("print_uploader_js"),
        uploaders = hqImport("hqmedia/js/uploaders");
    if (printUploader) {
        printTemplateUploader = uploaders.uploader(
            printUploader.slug,
            printUploader.options
        );
        printRef = hqImport('hqmedia/js/media_reference_models').BaseMediaReference(initialPageData.get('print_ref'));
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
