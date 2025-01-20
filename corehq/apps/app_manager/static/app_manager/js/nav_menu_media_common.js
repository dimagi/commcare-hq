hqDefine("app_manager/js/nav_menu_media_common", [
    "underscore",
    "hqwebapp/js/initial_page_data",
    "hqmedia/js/uploaders",
], function (
    _,
    initialPageData,
    uploadersModule,
) {
    let uploaders = {};

    _.each(initialPageData.get("multimedia_upload_managers"), function (uploader, type) {
        uploaders[type] = uploadersModule.uploader(
            uploader.slug,
            uploader.options
        );
    });

    return {
        audioUploader: uploaders.audio,
        iconUploader: uploaders.icon,
    };
});
