//not migrated now, else YUI wont be accessible as local variable for non migrated multimedia pages.
hqDefine('hqmedia/js/yui_config', function () {
    YUI.applyConfig({
        combine: false,
        fetchCSS: false,
        base: ['//',window.location.host,'/'].join(""),
        loaderPath: "static/hqmedia/MediaUploader/yui-loader.js",
    });
});
