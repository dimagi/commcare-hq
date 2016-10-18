/* globals FormplayerFrontend */

hqDefine('preview_app/js/preview_app.js', function() {

    var start = function(options) {

        $('#cloudcare-notifications').on('click', 'a', function(e) {
            // When opening a link in an iframe, need to ensure we are change the parent page
            $(this).attr('target', '_parent');
        });

        FormplayerFrontend.start(options);
    };

    return {
        start: start,
    };
});
