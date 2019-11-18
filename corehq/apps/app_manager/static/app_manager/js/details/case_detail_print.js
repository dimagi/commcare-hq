/* globals BaseMediaReference, HQMediaFileUploadController */
hqDefine("app_manager/js/details/case_detail_print", function () {
    var printRef, printTemplateUploader;
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
        print_uploader = initial_page_data("print_uploader_js");
    if (print_uploader) {
        printTemplateUploader = new HQMediaFileUploadController(
            print_uploader.slug,
            print_uploader.media_type,
            _.extend({}, print_uploader.options, {
                swfURL: initial_page_data('swfURL'),
                sessionid: initial_page_data('sessionid'),
            }));
        printTemplateUploader.init();
        printRef = hqImport('hqmedia/js/media_reference_models').BaseMediaReference(initial_page_data('print_ref'));
        printRef.upload_controller = printTemplateUploader;
        printRef.setObjReference(initial_page_data('print_media_info'));
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
