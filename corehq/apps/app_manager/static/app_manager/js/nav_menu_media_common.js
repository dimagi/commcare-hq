/* globals HQMediaFileUploadController */
hqDefine("app_manager/js/nav_menu_media_common.js", function() {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
        uploaders = {};

    _.each(initial_page_data("multimedia_upload_managers"), function(uploader, type) {
        uploaders[type] = new HQMediaFileUploadController(
            uploader.slug,
            uploader.media_type,
            _.extend({}, uploader.options, {
                sessionid: initial_page_data("sessionid"),
                swfURL: initial_page_data("swfURL"),
            })
        );
        uploaders[type].init();
    });

    return {
        audioUploader: uploaders.audio,
        iconUploader: uploaders.icon,
    };
});
