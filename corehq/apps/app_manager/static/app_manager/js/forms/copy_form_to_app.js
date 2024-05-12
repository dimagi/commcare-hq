"use strict";
hqDefine("app_manager/js/forms/copy_form_to_app", function () {
    "use strict";

    var module = function (moduleId, moduleName, isCurrentModule) {
        var self = {};
        self.id = moduleId;
        self.name = moduleName;
        self.isCurrent = isCurrentModule;
        return self;
    };

    var application = function (appId, appName, isCurrentApp, modules) {
        var self = {};
        self.id = appId;
        self.name = appName;
        self.isCurrent = isCurrentApp;
        self.modules = ko.observableArray(
            _.map(modules, function (mod) {
                return module(mod["module_id"], mod["name"], mod["is_current"]);
            })
        );
        var currentModule = _.find(self.modules(), function (mod) {
            return mod.isCurrent;
        });
        self.selectedModuleId = ko.observable(currentModule ? currentModule.id : undefined);
        return self;
    };

    var appsModulesModel = function (appsModules) {
        var self = {};
        self.apps = ko.observableArray(
            _.map(appsModules, function (app) {
                return application(app["app_id"], app["name"], app["is_current"], app["modules"]);
            })
        );
        var currentApp = _.find(self.apps(), function (app) {
            return app.isCurrent;
        });
        self.selectedAppId = ko.observable(currentApp ? currentApp.id : undefined);
        self.selectedApp = ko.computed(function () {
            return _.find(self.apps(), function (app) {
                return app.id === self.selectedAppId();
            });
        });
        return self;
    };

    $(function () {
        var $appModuleSelection = $("#app-module-selection");
        var viewModel = appsModulesModel(
            hqImport("hqwebapp/js/initial_page_data").get("apps_modules")
        );
        if ($appModuleSelection.length) {
            $appModuleSelection.koApplyBindings(viewModel);
        }
    });
});
