/*global FormplayerFrontend, Util */

FormplayerFrontend.module("AppSelect", function (AppSelect, FormplayerFrontend, Backbone, Marionette) {
    AppSelect.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps",
            "apps/:id": "selectApp",
            "apps/:id/menu": "listMenus",
            "apps/:apps/store": "storeApps",
        },
    });

    var API = {
        listApps: function () {
            FormplayerFrontend.request("clearForm");
            AppSelect.AppList.Controller.listApps();
        },
        selectApp: function (appId) {
            AppSelect.MenuList.Controller.selectMenu(appId);
        },
        storeApps: function (apps) {
            FormplayerFrontend.request("appselect:storeapps", apps);
        },
        listMenus: function (appId) {
            FormplayerFrontend.request("clearForm");
            var currentFragment = Backbone.history.getFragment();
            var steps = Util.getSteps(currentFragment);
            if (steps && steps.length > 0) {
                AppSelect.MenuList.Controller.selectMenu(appId, steps);
            } else {
                AppSelect.MenuList.Controller.selectMenu(appId);
            }
        },
        showDetail: function(model) {
            AppSelect.MenuList.Controller.showDetail(model);
        },
    };

    FormplayerFrontend.on("app:show:detail", function (model) {
        API.showDetail(model);
    });

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (appId) {
        FormplayerFrontend.navigate("apps/" + appId);
        API.selectApp(appId);
    });

    FormplayerFrontend.on("apps:storeapps", function (apps) {
        API.storeApps(apps);
    });

    FormplayerFrontend.on("menu:select", function (index, appId) {
        var newAddition;
        var oldRoute = Backbone.history.getFragment();
        if (oldRoute.indexOf("menu") < 0) {
            newAddition = "/menu?step=" + index;
        } else {
            newAddition = "&step=" + index;
        }
        FormplayerFrontend.navigate(oldRoute + newAddition);
        API.listMenus(appId);
    });

    AppSelect.on("start", function () {
        new AppSelect.Router({
            controller: API,
        });
    });

});