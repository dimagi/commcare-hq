hqDefine('notifications/js/manage_notifications', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    $(function () {
        $('#ko-alert-container').koApplyBindings({
            alerts: initialPageData.get('alerts'),
        });
    });
});
