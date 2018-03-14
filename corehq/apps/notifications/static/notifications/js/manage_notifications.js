hqDefine('notifications/js/manage_notifications', function() {
$(function () {
    $('#ko-alert-container').koApplyBindings({
        alerts: {{ alerts|JSON }}
    });
});
});
