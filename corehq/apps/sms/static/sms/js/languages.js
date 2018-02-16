hqDefine('sms/js/languages', function() {
    $(function () {
        var langs = {{ sms_langs|JSON }};
        var saveURL = "{% url "edit_sms_languages" domain %}";
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
