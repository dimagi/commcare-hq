hqDefine('app_manager/js/summary/form_summary',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'app_manager/js/summary/models',
    'app_manager/js/summary/form_models',
    'app_manager/js/summary/utils',
    'app_manager/js/menu',  // enable lang switcher and "Updates to publish" banner
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // popover
    'hqwebapp/js/bootstrap3/components.ko',    // search box
], function ($, _, ko, initialPageData, assertProperties, models, formModels, utils) {
    $(function () {
        var lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        var formSummaryMenu = models.menuModel({
            items: _.map(initialPageData.get("modules"), function (module) {
                return models.menuItemModel({
                    unique_id: module.unique_id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    has_errors: false,
                    subitems: _.map(module.forms, function (form) {
                        return models.menuItemModel({
                            unique_id: form.unique_id,
                            name: utils.translateName(form.name, lang, langs),
                            icon: utils.formIcon(form),
                        });
                    }),
                });
            }),
            viewAllItems: gettext("View All Forms"),
        });

        var formSummaryContent = formModels.formSummaryModel({
            errors: initialPageData.get("errors"),
            form_name_map: initialPageData.get("form_name_map"),
            lang: lang,
            langs: langs,
            modules: initialPageData.get("modules"),
            read_only: initialPageData.get("read_only"),
            appId: initialPageData.get("app_id"),
        });

        var formSummaryController = formModels.formSummaryControlModel([formSummaryContent]);
        models.initVersionsBox(
            $("#version-selector"),
            {id: initialPageData.get("app_id"), text: initialPageData.get("app_version")}
        );
        $("#form-summary-header").koApplyBindings(formSummaryController);
        models.initMenu([formSummaryContent], formSummaryMenu);
        models.initSummary(formSummaryContent, formSummaryController, "#form-summary");
    });
});
