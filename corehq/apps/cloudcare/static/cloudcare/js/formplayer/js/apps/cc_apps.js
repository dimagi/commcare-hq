FormplayerFrontend.module("AppSelect", function (AppSelect, FormplayerFrontend, Backbone, Marionette, $, _) {
    AppSelect.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps/:apps": "listApps",
            "apps/:id/select": "selectApp",
            "apps/:apps/store": "storeApps"
        }
    });

    var API = {
        listApps: function () {
            AppSelect.AppList.Controller.listApps();
        },
        selectApp: function (model) {
            AppSelect.MenuList.Controller.listMenus(model);
        },
        storeApps: function (apps) {
            FormplayerFrontend.request("appselect:storeapps", apps)
        },
        selectMenu: function(model) {
            AppSelect.MenuList.Controller.selectMenu(model);
        }
    };

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (model) {
        FormplayerFrontend.navigate("apps/" + model.attributes._id + "/select");
        API.selectApp(model);
    });

    FormplayerFrontend.on("apps:storeapps", function (apps) {
        API.storeApps(apps);
        FormplayerFrontend.navigate("apps");
    });

    FormplayerFrontend.on("menu:select", function (model) {
        API.selectMenu(model);
        FormplayerFrontend.navigate("model");
    });

    AppSelect.on("start", function () {
        new AppSelect.Router({
            controller: API
        });
    });

});