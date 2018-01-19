hqDefine("app_manager/js/nav_menu_media_common", [
    'underscore',
    'hqwebapp/js/initial_page_data',
], function(
    _,
    initialPageData
) {
    var uploaders = {};

    _.each(initialPageData.get("multimedia_upload_managers"), function(uploader, type) {
        uploaders[type] = new hqImport("hqmedia/MediaUploader/hqmedia.upload_controller.js").HQMediaFileUploadController(
            uploader.slug,
            uploader.media_type,
            _.extend({}, uploader.options, {
                sessionid: initialPageData.get("sessionid"),
                swfURL: initialPageData.get("swfURL"),
            })
        );
        uploaders[type].init();
    });

    return {
        audioUploader: uploaders.audio,
        iconUploader: uploaders.icon,
    };
});
