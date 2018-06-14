/* globals hqDefine, ko, _ */
hqDefine("app_manager/js/forms/copy_form_to_app", function () {
    "use strict";

    var module = function (moduleId, moduleName) {
        var self = {};
        self.id = moduleId;
        self.name = moduleName;
        return self;
    };

    var application = function (appId, appName, modules) {
        var self = {};
        self.id = appId;
        self.name = appName;
        self.modules = ko.observableArray(
            _.map(modules, function (mod) {
                return module(mod["module_id"], mod["name"]);
            })
        );
        return self;
    }

    var appsModulesModel = function (appsModules) {
        var self = {};
        self.apps = ko.observableArray(
            _.map(appsModules, function (app) {
                return application(app["app_id"], app["name"], app["modules"]);
            })
        );
        self.selectedAppId = ko.observable(self.apps()[0].id);
        self.selectedApp = ko.computed(function () {
            var selected = _.filter(self.apps(), function (app) {
                return app.id === self.selectedAppId();
            });
            return selected.length ? selected[0] : undefined;
        });
        return self;
    };

    $(function () {
        var $appModuleSelection = $("#app-module-selection");
        var viewModel = appsModulesModel(
            hqImport("hqwebapp/js/initial_page_data").get("apps_modules"),
        );
        if ($appModuleSelection.length) {
            $appModuleSelection.koApplyBindings(viewModel);
        }
    });
});
