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
    'hqwebapp/js/knockout_bindings.ko', // popover
    'hqwebapp/js/components.ko',    // search box
], function ($, _, ko, initialPageData, assertProperties, models, formModels, utils, layout) {

    $(function () {
        var lang = initialPageData.get('lang'),
            langs = initialPageData.get('langs');

        var resizeViewPort = function () {
            var availableHeight = layout.getAvailableContentHeight();
            $("#form-summary-diff").css('height', availableHeight);
        };
        resizeViewPort();

        $(window).resize(function(){ resizeViewPort(); });


        var firstModulesAndFormsIdsByID = {};
        _.each(initialPageData.get('first.modules'), function (module) {
            firstModulesAndFormsIdsByID[module.id] = _.pluck(module.forms, 'id');
        });

        var secondModulesAndFormsIdsByID = {};
        _.each(initialPageData.get('second.modules'), function (module) {
            secondModulesAndFormsIdsByID[module.id] = _.pluck(module.forms, 'id');
        });

        var getModuleIntersection = function () {
            // returns a list of all modules and forms from both versions

            // deep copy these datastructures so we don't overwrite the underlying data
            var allModules = firstModules = JSON.parse(JSON.stringify(initialPageData.get('first.modules'))),
                secondModules = JSON.parse(JSON.stringify(initialPageData.get('second.modules'))),
                firstModulesById = _.indexBy(firstModules, 'id'),
                secondModulesById = _.indexBy(secondModules, 'id');

            // For modules that exist in both versions, ensure the forms from the both versions are represented
            _.each(secondModules, function (secondModule) {
                var firstModule = firstModulesById[secondModule.id];
                if (firstModule) {
                    // both versions have this module, add forms from second that aren't in first
                    var firstModuleFormIds = _.pluck(firstModule.forms, 'id'),
                        secondModuleFormsById = _.indexBy(secondModule.forms, 'id'),
                        inSecondNotFirst = _.difference(_.keys(secondModuleFormsById), firstModuleFormIds);
                    _.each(inSecondNotFirst, function (extraFormId) {
                        firstModule.forms.push(secondModuleFormsById[extraFormId]);
                    });
                } else {
                    // this module didn't exist in the first version
                    allModules.push(secondModule);
                }
            });
            return allModules;
        };

        var getModuleVersions = function (module) {
            var versions = [];
            if (module.id in firstModulesAndFormsIdsByID) {
                versions.push(initialPageData.get('first.app_version'));
            }
            if (module.id in secondModulesAndFormsIdsByID) {
                versions.push(initialPageData.get('second.app_version'));
            }
            return versions;
        };

        var getFormVersions = function (module, form) {
            var versions = [];
             if (module.id in firstModulesAndFormsIdsByID && firstModulesAndFormsIdsByID[module.id].includes(form.id)) {
                versions.push(initialPageData.get('first.app_version'));
            }
            if (module.id in secondModulesAndFormsIdsByID && secondModulesAndFormsIdsByID[module.id].includes(form.id)) {
                versions.push(initialPageData.get('second.app_version'));
            }
            return versions;
        };


        var formSummaryMenu = models.menuModel({
            items: _.map(getModuleIntersection(), function (module) {
                return models.menuItemModel({
                    id: module.id,
                    name: utils.translateName(module.name, lang, langs),
                    icon: utils.moduleIcon(module),
                    versions: getModuleVersions(module),
                    has_errors: false,
                    subitems: _.map(module.forms, function (form) {
                        return models.menuItemModel({
                            id: form.id,
                            name: utils.translateName(form.name, lang, langs),
                            icon: utils.formIcon(form),
                            versions: getFormVersions(module, form),
                        });
                    }),
                });
            }),
            viewAllItems: gettext("View All Forms"),
        });


        var firstFormSummaryContent = formModels.formSummaryModel({
            errors: initialPageData.get("first.errors"),
            form_name_map: initialPageData.get("form_name_map"),
            lang: lang,
            langs: langs,
            modules: initialPageData.get("first.modules"),
            read_only: initialPageData.get("first.read_only"),
        });

        var secondFormSummaryContent = formModels.formSummaryModel({
            errors: initialPageData.get("second.errors"),
            form_name_map: initialPageData.get("form_name_map"),
            lang: lang,
            langs: langs,
            modules: initialPageData.get("second.modules"),
            read_only: initialPageData.get("second.read_only"),
        });


        var formSummaryController = formModels.formSummaryControlModel([firstFormSummaryContent, secondFormSummaryContent]);
        $("#form-summary-header").koApplyBindings(formSummaryController);
        models.initMenu([firstFormSummaryContent, secondFormSummaryContent], formSummaryMenu);
        models.initSummary(firstFormSummaryContent, formSummaryController, "#first-app-summary");
        models.initSummary(secondFormSummaryContent, formSummaryController, "#second-app-summary");
    });
});
