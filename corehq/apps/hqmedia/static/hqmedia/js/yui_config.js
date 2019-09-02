hqDefine('hqmedia/js/yui_config', function () {
    YUI.applyConfig({
        combine: false,
        fetchCSS: false,
        base: ['//',window.location.host,'/'].join(""),
        loaderPath: "static/hqmedia/MediaUploader/yui-loader.js",
    });
});
