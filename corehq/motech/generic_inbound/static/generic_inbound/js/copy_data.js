hqDefine('generic_inbound/js/copy_data', [
    'hqwebapp/js/bootstrap3/alert_user',
], function (alertUserModule) {
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
});
