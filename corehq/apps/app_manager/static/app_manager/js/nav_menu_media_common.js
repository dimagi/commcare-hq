hqDefine("app_manager/js/nav_menu_media_common", function () {
    const initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        uploadersModule = hqImport("hqmedia/js/hqmediauploaders");
    let uploaders = {};

    _.each(initialPageData.get("multimedia_upload_managers"), function (uploader, type) {
        uploaders[type] = uploadersModule.uploader(
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
