hqDefine("app_manager/js/details/case_detail_print", function() {
    var print_ref, printTemplateUploader;
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
        print_uploader = initial_page_data("print_uploader_js");
    if (print_uploader) {
        printTemplateUploader = new hqImport("hqmedia/MediaUploader/hqmedia.upload_controller.js").HQMediaFileUploadController (
            print_uploader.slug,
            print_uploader.media_type,
            _.extend({}, print_uploader.options, {
                swfURL: initial_page_data('swfURL'),
                sessionid: initial_page_data('sessionid'),
            }));
        printTemplateUploader.init();
        print_ref = new BaseMediaReference(initial_page_data('print_ref'));
        print_ref.upload_controller = printTemplateUploader;
        print_ref.setObjReference(initial_page_data('print_media_info'));
        printTemplateUploader.currentReference = print_ref;
    }

    return {
        getPrintRef: function() {
            return print_ref;
        },
        getPrintTemplateUploader: function() {
            return printTemplateUploader;
        },
    };
});
