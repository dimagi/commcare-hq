hqDefine("app_manager/js/app_view_settings.js", function() {
    $(function () {
        var CommcareSettings = hqImport('app_manager/js/commcaresettings.js').CommcareSettings;
        COMMCAREHQ.appView.settings = new CommcareSettings(COMMCAREHQ.appView.settings);
        $('#commcare-settings').koApplyBindings(COMMCAREHQ.appView.settings);
    });
});
