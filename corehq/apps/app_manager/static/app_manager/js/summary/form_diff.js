hqDefine('app_manager/js/summary/form_diff',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'app_manager/js/summary/models',
    'app_manager/js/summary/form_models',
    'app_manager/js/summary/utils',
    'hqwebapp/js/layout',
    'app_manager/js/menu',  // enable lang switcher and "Updates to publish" banner
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // popover
    'hqwebapp/js/bootstrap3/components.ko',    // search box
], function ($, _, ko, initialPageData, assertProperties, models, formModels, utils, layout) {

    $(function () {
        var lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        var resizeViewPort = function () {
            var availableHeight = layout.getAvailableContentHeight();
            $("#form-summary-diff").css('height', availableHeight);
        };
        resizeViewPort();

        $(window).resize(function () {
            resizeViewPort();
        });

        var getModuleIntersection = function () {
            // returns a list of all modules and forms from both versions

            // deep copy these datastructures so we don't overwrite the underlying data
            var firstModules = JSON.parse(JSON.stringify(initialPageData.get('first.modules'))),
                secondModules = JSON.parse(JSON.stringify(initialPageData.get('second.modules'))),
                firstModulesById = _.indexBy(firstModules, 'unique_id'),
                allModules = firstModules;
            // given the list of modules in the first list
            // if the element from the second is in the first, check the forms, and label them
            // otherwise just add the second element
            _.each(secondModules, function (secondModule) {
                var firstModule = firstModulesById[secondModule.unique_id];
                if (firstModule) { // both versions have this module, check that all the forms are the same
                    // find all forms;
                    var firstModuleFormIds = _.pluck(firstModule.forms, 'unique_id'),
                        secondModuleFormsById = _.indexBy(secondModule.forms, 'unique_id'),
                        inSecondNotFirst = _.difference(_.keys(secondModuleFormsById), firstModuleFormIds);
                    _.each(inSecondNotFirst, function (extraFormId) {
                        firstModule.forms.push(secondModuleFormsById[extraFormId]);
                    });
                } else {
                    allModules.push(secondModule);
                }
            });
            return allModules;
        };

        var formSummaryMenu = models.menuModel({
            items: _.map(getModuleIntersection(), function (module) {
                return models.menuItemModel({
                    unique_id: module.unique_id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    has_changes: module.changes.contains_changes,
                    has_errors: false,
                    subitems: _.map(module.forms, function (form) {
                        return models.menuItemModel({
                            unique_id: form.unique_id,
                            name: utils.translateName(form.name, lang, langs),
                            icon: utils.formIcon(form),
                            has_changes: form.changes.contains_changes,
                        });
                    }),
                });
            }),
            viewAllItems: gettext("View All Forms"),
            viewChanged: gettext("View Changed Items"),
        });


        var firstFormSummaryContent = formModels.formSummaryModel({
            errors: initialPageData.get("first.errors"),
            form_name_map: initialPageData.get("form_name_map"),
            lang: lang,
            langs: langs,
            modules: initialPageData.get("first.modules"),
            read_only: initialPageData.get("first.read_only"),
            appId: initialPageData.get("first.app_id"),
        });

        var secondFormSummaryContent = formModels.formSummaryModel({
            errors: initialPageData.get("second.errors"),
            form_name_map: initialPageData.get("form_name_map"),
            lang: lang,
            langs: langs,
            modules: initialPageData.get("second.modules"),
            read_only: initialPageData.get("second.read_only"),
            appId: initialPageData.get("second.app_id"),
        });


        var formSummaryController = formModels.formSummaryControlModel([firstFormSummaryContent, secondFormSummaryContent], true);

        $("#form-summary-header").koApplyBindings(formSummaryController);
        models.initVersionsBox(
            $("#first-version-selector"),
            {id: initialPageData.get("first.app_id"), text: initialPageData.get("first.app_version")}
        );
        models.initVersionsBox(
            $("#second-version-selector"),
            {id: initialPageData.get("second.app_id"), text: initialPageData.get("second.app_version")}
        );

        models.initMenu([firstFormSummaryContent, secondFormSummaryContent], formSummaryMenu);
        models.initSummary(firstFormSummaryContent, formSummaryController, "#first-app-summary");
        models.initSummary(secondFormSummaryContent, formSummaryController, "#second-app-summary");
    });
});
