hqDefine("hqwebapp/js/maintenance_alerts", function() {
    $(function() {
        $('#ko-alert-container').koApplyBindings({
            alerts: hqImport("hqwebapp/js/initial_page_data").get('alerts'),
        });
    });
});
