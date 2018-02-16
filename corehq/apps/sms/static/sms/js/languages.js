hqDefine('sms/js/languages', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    $(function () {
        var langs = initialPageData.get('sms_langs');
        var saveURL = initialPageData.reverse("edit_sms_languages");
        var edit = true;
        var validate = true;
        var SupportedLanguages = hqImport('app_manager/js/supported_languages').SupportedLanguages;
        var sl = new SupportedLanguages({
            langs: langs,
            saveURL: saveURL,
            edit: edit,
            validate: validate
        });
        $("#supported-languages").koApplyBindings(sl);
    });
});
