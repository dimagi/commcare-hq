import initialPageData from "hqwebapp/js/initial_page_data";
import uploaders from "hqmedia/js/uploaders";
import mediaReferenceModels from "hqmedia/js/media_reference_models";

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

export default {
    getPrintRef: function () {
        return printRef;
    },
    getPrintTemplateUploader: function () {
        return printTemplateUploader;
    },
};
