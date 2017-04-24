hqDefine("app_manager/js/app_view_settings.js", function() {
    $(function () {
        var CommcareSettings = hqImport('app_manager/js/commcaresettings.js').CommcareSettings;
        COMMCAREHQ.appView.settings = new CommcareSettings(COMMCAREHQ.appView.settings);
        $('#commcare-settings').koApplyBindings(COMMCAREHQ.appView.settings);

        // Set up typeahead for domain names
        $("#id_domain").koApplyBindings({
            domain_names: hqImport("hqwebapp/js/initial_page_data.js").get("domain_names"),
        });

        // Multimedia analytics
        $(document).on("click", '#download_zip', function() {
            ga_track_event('App Builder', 'Download Multimedia');
        });
        $(document).on("click", '#open_checker', function() {
            ga_track_event('App Builder', 'Manage Multimedia');
        });
    });
});
