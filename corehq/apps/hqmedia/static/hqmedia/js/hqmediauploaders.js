/* globals HQMediaUploaderTypes */
hqDefine("hqmedia/js/hqmediauploaders",[
    "hqwebapp/js/initial_page_data",
    "underscore",
    'file-uploader',
    'yui-base',
], function (intialPageData,_, HQMediaUploaderTypes,YUI) {
    var HQMediaUploaders = {};  // This will be referenced by the media references
    _.each(intialPageData.get("uploaders"), function (uploader) {
        HQMediaUploaders[uploader.slug] = new HQMediaUploaderTypes[uploader.uploader_type](
            uploader.slug,
            uploader.media_type,
            _.extend({
                sessionid: intialPageData.get("sessionid"),
                swfURL: intialPageData.get("swfURL"),
            }, uploader.options));

        YUI.applyConfig({
            combine: false,
            fetchCSS: false,
            base: ['//',window.location.host,'/'].join(""),
        });
        HQMediaUploaders[uploader.slug].init();
    });

    var get = function () {
        return HQMediaUploaders;
    };

    return {
        get: get,
    };
});
