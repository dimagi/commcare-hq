import $ from "jquery";
import FormplayerFrontend from "cloudcare/js/formplayer/app";

function start(options) {

    $('#cloudcare-notifications').on('click', 'a', function () {
        // When opening a link in an iframe, need to ensure we are change the parent page
        $(this).attr('target', '_parent');
    });

    FormplayerFrontend.getXSRF(options).then(() => FormplayerFrontend.start(options));

    if (localStorage.getItem("preview-tablet")) {
        FormplayerFrontend.trigger('view:tablet');
    } else {
        FormplayerFrontend.trigger('view:phone');
    }
}

export {
    start,
};
