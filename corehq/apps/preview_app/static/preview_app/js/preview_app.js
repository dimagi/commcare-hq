/* globals FormplayerFrontend */

hqDefine('preview_app/js/preview_app.js', function() {

    var start = function(options) {
        FormplayerFrontend.start(options);
    };

    return {
        start: start,
    };
});
