hqDefine("hqwebapp/js/maintenance_alerts",[
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/widgets',
], function ($, initialPageData) {
    $(function () {
        $('#ko-alert-container').koApplyBindings({
            alerts: initialPageData.get('alerts'),
        });
    });
});
