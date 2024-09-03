hqDefine("hqmedia/js/hqmediauploaders", function () {
    var uploadController = hqImport("hqmedia/MediaUploader/hqmedia.upload_controller");
    var HQMediaUploaders = {};  // This will be referenced by the media references
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;
    _.each(initial_page_data("uploaders"), function (uploader) {
        HQMediaUploaders[uploader.slug] = new uploadController[uploader.uploader_type](
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
