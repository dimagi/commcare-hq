/* globals HQMediaUploaderTypes */
hqDefine("hqmedia/js/hqmediauploaders.js", function() {
    var HQMediaUploaders = {};  // This will be referenced by the media references
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get;
    _.each(initial_page_data("uploaders"), function(uploader) {
        HQMediaUploaders[uploader.slug] = new HQMediaUploaderTypes[uploader.uploader_type] (
            uploader.slug,
            uploader.media_type,
            _.extend({
                sessionid: initial_page_data("sessionid"),
                swfURL: initial_page_data("swfURL"),
            }, uploader.options));
        HQMediaUploaders[uploader.slug].init();
    });

    var get = function() {
        return HQMediaUploaders;
    };

    return {
        get: get,
    };
});
