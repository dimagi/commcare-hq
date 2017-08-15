/* globals FormplayerFrontend */

hqDefine('cloudcare/js/preview_app/preview_app', function() {

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
