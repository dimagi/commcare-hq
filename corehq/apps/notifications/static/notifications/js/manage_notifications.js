hqDefine('notifications/js/manage_notifications', [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    $(function () {
        $('#ko-alert-container').koApplyBindings({
            alerts: initialPageData.get('alerts'),
        });
    });
});
