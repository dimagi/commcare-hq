(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define('hqmedia/js/yui_config', ['yui-base'], factory);
    } else {
        factory(YUI);
    }
})(this, function (YUI) {

    YUI.applyConfig({
        combine: false,
        fetchCSS: false,
        base: ['//',window.location.host,'/'].join(""),
        loaderPath: "static/hqmedia/MediaUploader/yui-loader.js",
    });
});
