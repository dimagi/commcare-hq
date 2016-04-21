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
        console.log("Navigating");
        FormplayerFrontend.navigate("apps/" + model.attributes._id);
        API.selectApp(model);
    });

    FormplayerFrontend.on("apps:storeapps", function (apps) {
        API.storeApps(apps);
    });

    FormplayerFrontend.on("menu:select", function (model) {
        API.selectMenu(model);
        FormplayerFrontend.navigate("apps/" + model.collection.app_id + "/menu/" + model.attributes.index);
    });

    AppSelect.on("start", function () {
        new AppSelect.Router({
            controller: API
        });
    });

});