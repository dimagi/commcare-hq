import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import supportedLanguages from "app_manager/js/supported_languages";

$(function () {
    var langs = initialPageData.get('sms_langs');
    var saveURL = initialPageData.reverse("edit_sms_languages");
    var edit = true;
    var validate = true;
    var sl = supportedLanguages.SupportedLanguages({
        langs: langs,
        saveURL: saveURL,
        edit: edit,
        validate: validate,
    });
    $("#supported-languages").koApplyBindings(sl);
});
