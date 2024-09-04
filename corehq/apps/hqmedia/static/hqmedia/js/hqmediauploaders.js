hqDefine("hqmedia/js/hqmediauploaders", [
    'underscore',
    'hqmedia/MediaUploader/hqmedia.upload_controller',
    'hqwebapp/js/initial_page_data',
], function (
    _,
    HQMediaUploaderTypes,
    initialPageData
) {
    var HQMediaUploaders = {};  // This will be referenced by the media references
    _.each(initialPageData.get("uploaders"), function (uploader) {
        HQMediaUploaders[uploader.slug] = new HQMediaUploaderTypes[uploader.uploader_type](
            uploader.slug,
            uploader.media_type,
            uploader.options
        );
        HQMediaUploaders[uploader.slug].init();
    });

    var get = function () {
        return HQMediaUploaders;
    };

    return {
        get: get,
    };
});
