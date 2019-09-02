hqDefine("hqmedia/js/hqmediauploaders",[
    "hqwebapp/js/initial_page_data",
    "underscore",
    'file-uploader',
], function (intialPageData, _, HQMediaUploaderTypes) {
    var HQMediaUploaders = {};  // This will be referenced by the media references
    _.each(intialPageData.get("uploaders"), function (uploader) {
        HQMediaUploaders[uploader.slug] = new HQMediaUploaderTypes[uploader.uploader_type](
            uploader.slug,
            uploader.media_type,
            _.extend({
                sessionid: intialPageData.get("sessionid"),
                swfURL: intialPageData.get("swfURL"),
            }, uploader.options));
        HQMediaUploaders[uploader.slug].init();
    });

    var get = function () {
        return HQMediaUploaders;
    };

    return {
        get: get,
    };
});
