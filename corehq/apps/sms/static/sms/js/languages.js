hqDefine('sms/js/languages',[
    "jquery",
    "hqwebapp/js/initial_page_data",
    "app_manager/js/supported_languages",
], function($, initialPageData, supportedLanguages) {
    $(function () {
        var langs = initialPageData.get('sms_langs');
        var saveURL = initialPageData.reverse("edit_sms_languages");
        var edit = true;
        var validate = true;
        var SupportedLanguages = supportedLanguages.SupportedLanguages;
        var sl = new SupportedLanguages({
            langs: langs,
            saveURL: saveURL,
            edit: edit,
            validate: validate,
        });
        $("#supported-languages").koApplyBindings(sl);
    });
});
