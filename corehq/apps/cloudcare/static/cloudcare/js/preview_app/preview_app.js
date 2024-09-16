'use strict';
hqDefine('cloudcare/js/preview_app/preview_app', [
    'jquery',
    'cloudcare/js/formplayer/app',
], function (
    $,
    FormplayerFrontend
) {
    var start = function (options) {

        $('#cloudcare-notifications').on('click', 'a', function () {
            // When opening a link in an iframe, need to ensure we are change the parent page
            $(this).attr('target', '_parent');
        });

        FormplayerFrontend.getXSRF(options).then(() =>
            FormplayerFrontend.start(options)
        );

        if (localStorage.getItem("preview-tablet")) {
            FormplayerFrontend.trigger('view:tablet');
        } else {
            FormplayerFrontend.trigger('view:phone');
        }
    };

    return {
        start: start,
    };
});
