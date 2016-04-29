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
            if (currentFragment.indexOf("menu") < 0) {
                AppSelect.MenuList.Controller.selectMenu(app_id);
            } else {
                urlParams = Util.getQueryParams(currentFragment);
                steps = [];
                for(var i = 0; i < urlParams.length; i++){
                    steps.push(urlParams[i].v)
                }
                AppSelect.MenuList.Controller.selectMenu(app_id, steps);
            }
        },
        selectMenu: function (app_id, index) {
            currentFragment = Backbone.history.getFragment();

            if (currentFragment.indexOf("menu") < 0) {
                newAddition = "/menu?step=" + index
                AppSelect.MenuList.Controller.selectMenu(app_id, index);
            } else {
                newAddition = "&step=" + index;
                var steps = [];
                currentFragment.split("&").forEach(function (part) {
                    var item = part.split("=");
                    steps.push(item[2]);
                });
                steps.push(index);
                AppSelect.MenuList.Controller.selectMenu(app_id, select_list);
            }
            return currentFragment + newAddition;
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

    FormplayerFrontend.on("menu:select", function (model) {
        oldRoute = Backbone.history.getFragment();

        if (oldRoute.indexOf("menu") < 0) {
            newAddition = "/menu?step=" + model.attributes.index;
        } else {
            newAddition = "&step=" + model.attributes.index;
        }

        FormplayerFrontend.navigate(oldRoute + newAddition);
        API.listMenus(model.collection.app_id);
    });

    AppSelect.on("start", function () {
        new AppSelect.Router({
            controller: API
        });
    });

});