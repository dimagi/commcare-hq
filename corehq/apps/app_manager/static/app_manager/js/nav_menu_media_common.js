/* globals HQMediaFileUploadController */
hqDefine("app_manager/js/nav_menu_media_common", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        uploaders = {};

    _.each(initialPageData.get("multimedia_upload_managers"), function (uploader, type) {
        uploaders[type] = new HQMediaFileUploadController(
            uploader.slug,
            uploader.media_type,
            uploader.options
        );
        uploaders[type].init();
    });

    return {
        audioUploader: uploaders.audio,
        iconUploader: uploaders.icon,
    };
});
