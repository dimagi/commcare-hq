FormplayerFrontend.module("AppSelect", function (AppSelect, FormplayerFrontend, Backbone, Marionette, $, _) {
    AppSelect.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps",
            "apps/:id": "selectApp",
            "apps/:id/menu": "listMenus",
            "apps/:apps/store": "storeApps"
        }
    });

    var API = {
        listApps: function () {
            AppSelect.AppList.Controller.listApps();
        },
        selectApp: function (app_id) {
            AppSelect.MenuList.Controller.selectMenu(app_id);
        },
        storeApps: function (apps) {
            FormplayerFrontend.request("appselect:storeapps", apps)
        },
        listMenus: function (app_id) {
            currentFragment = Backbone.history.getFragment();
            steps = Util.getSteps(currentFragment);
            if (steps && steps.length > 0) {
                AppSelect.MenuList.Controller.selectMenu(app_id, steps);
            } else {
                AppSelect.MenuList.Controller.selectMenu(app_id);
            }
        },
        showDetail: function(model) {
            AppSelect.MenuList.Controller.showDetail(model);
        }
    };

    FormplayerFrontend.on("app:show:detail", function (model) {
        API.showDetail(model);
    });

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (app_id) {
        FormplayerFrontend.navigate("apps/" + app_id);
        API.selectApp(app_id);
    });

    FormplayerFrontend.on("apps:storeapps", function (apps) {
        API.storeApps(apps);
    });

    FormplayerFrontend.on("menu:select", function (index, appId) {
        oldRoute = Backbone.history.getFragment();
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