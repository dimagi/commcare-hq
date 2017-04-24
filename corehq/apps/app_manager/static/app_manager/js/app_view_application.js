hqDefine("app_manager/js/app_manager_application.js", function() {
    $(function() {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data.js").get,
            reverse = hqImport("hqwebapp/js/urllib.js").reverse;

        var $translation_ui = $("#translations_ui");
        mk_translation_ui({
            translations: initial_page_data("translations"),
            url: reverse("edit_app_ui_translations"),
            suggestion_url: reverse("get_app_ui_translations"),
            lang: initial_page_data("lang"),
            allow_autofill: initial_page_data("lang") !== 'en',
            $home: $translation_ui
        });
    });
});
