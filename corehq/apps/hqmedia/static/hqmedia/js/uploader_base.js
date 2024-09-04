hqDefine("hqmedia/js/uploader_base", [
    'hqwebapp/js/initial_page_data',
], function (initialPageData) {
    YUI_config = {
        combine: false,
        fetchCSS: false,
        base: "//" + initialPageData.get("host") + "/",
        loaderPath: "static/hqmedia/MediaUploader/yui-loader.js"
    };
    require([
        'hqmedia/MediaUploader/yui-base',
        'hqmedia/MediaUploader/yui-uploader',
        'hqmedia/MediaUploader/hqmedia.upload_controller',
        'hqmedia/js/hqmediauploaders',
    ], function () {
        // nothing to do here
    });
});
