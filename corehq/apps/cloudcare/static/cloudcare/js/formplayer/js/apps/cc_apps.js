FormplayerFrontend.module("AppSelect", function (AppSelect, FormplayerFrontend, Backbone, Marionette, $, _) {
    AppSelect.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps",
            "apps/:id": "selectApp",
            "apps/:id/menu/:menuId": "selectMenu",
            "apps/:apps/store": "storeApps"
        }
    });

    var API = {
        listApps: function () {
            AppSelect.AppList.Controller.listApps();
        },
        selectApp: function (app_id) {
            AppSelect.MenuList.Controller.listMenus(app_id);
        },
        storeApps: function (apps) {
            FormplayerFrontend.request("appselect:storeapps", apps)
        },
        selectMenu: function(id, menuId) {
            AppSelect.MenuList.Controller.selectMenu(menuId);
        }
    };

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (app_id) {
        console.log("Navigating");
        FormplayerFrontend.navigate("apps/" + app_id);
        API.selectApp(app_id);
    });

    FormplayerFrontend.on("apps:storeapps", function (apps) {
        API.storeApps(apps);
    });

    FormplayerFrontend.on("menu:select", function (model) {
        API.selectMenu(model.collection.app_id, model.attributes.index);
        FormplayerFrontend.navigate("apps/" + model.collection.app_id + "/menu/" + model.attributes.index);
    });

    AppSelect.on("start", function () {
        new AppSelect.Router({
            controller: API
        });
    });

});