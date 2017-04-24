/* Behavior for app_view.html, regardless of document type (i.e., applies to both normal and remote apps) */
hqDefine("app_manager/js/app_view.js", function() {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
            reverse = hqImport("hqwebapp/js/urllib.js").reverse;

        // Settings
        var CommcareSettings = hqImport('app_manager/js/commcaresettings.js').CommcareSettings;
        COMMCAREHQ.appView.settings = new CommcareSettings(COMMCAREHQ.appView.settings);
        $('#commcare-settings').koApplyBindings(COMMCAREHQ.appView.settings);

        // Languages
        var SupportedLanguages = hqImport('app_manager/js/supported-languages.js').SupportedLanguages;
        $("#supported-languages").koApplyBindings(new SupportedLanguages({
            langs: initial_page_data("langs"),
            saveURL: reverse("edit_app_langs"),
            validate: !initial_page_data("is_remote_app"),
        }));

        // Set up typeahead for domain names when copying app
        $("#id_domain").koApplyBindings({
            domain_names: initial_page_data("domain_names"),
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
