import alertUserModule from "hqwebapp/js/bootstrap5/alert_user";

let alertUser = alertUserModule.alert_user;

window.copyData = function (elementId) {
    let range = document.createRange();
    range.selectNode(document.getElementById(elementId));
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    const copied = document.execCommand('copy');
    window.getSelection().removeAllRanges();
    if (copied) {
        alertUser(gettext("URL Copied"), "success", true);
    }
};
