/*global FormplayerFrontend, Util */

FormplayerFrontend.module("SessionNavigate", function (SessionNavigate, FormplayerFrontend, Backbone, Marionette) {
    SessionNavigate.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps", // list all apps available to this user
            "apps/:id": "selectApp", // select the app under :id and list root commands
            "apps/:id/menu": "listMenus", // select the app under :id, make session steps in params, display screen
        },
    });

    var API = {
        listApps: function () {
            FormplayerFrontend.request("clearForm");
            SessionNavigate.AppList.Controller.listApps();
        },
        selectApp: function (appId) {
            SessionNavigate.MenuList.Controller.selectMenu(appId);
        },
        listMenus: function (appId) {
            FormplayerFrontend.request("clearForm");
            var currentFragment = Backbone.history.getFragment();
            var paramMap = Util.getSteps(currentFragment);
            var steps = paramMap.steps;
            var page = paramMap.page || 0;
            var search = paramMap.search || "";
            SessionNavigate.MenuList.Controller.selectMenu(appId, steps, page, search);
        },
        showDetail: function (model) {
            SessionNavigate.MenuList.Controller.showDetail(model);
        },
    };

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (appId) {
        FormplayerFrontend.navigate("apps/" + appId);
        API.selectApp(appId);
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

    FormplayerFrontend.on("menu:paginate", function (index, appId) {
        var newAddition = "&page=" + index;
        var oldRoute = Backbone.history.getFragment();
        // "page" param should always be at the end of the URL
        if (oldRoute.indexOf('page') > 0) {
            oldRoute = oldRoute.substring(0, oldRoute.indexOf('&page'));
        }
        FormplayerFrontend.navigate(oldRoute + newAddition);
        API.listMenus(appId);
    });

    FormplayerFrontend.on("menu:search", function (searchText, appId) {
        var newAddition = "&search=" + searchText;
        var oldRoute = Backbone.history.getFragment();
        // If we have a "oage" param, wipe it out (pagination is reset on search)
        if (oldRoute.indexOf('page') > 0) {
            oldRoute = oldRoute.substring(0, oldRoute.indexOf('&page'));
        }
        // If we have a previous "search" param wipe it out
        if (oldRoute.indexOf('search') > 0) {
            oldRoute = oldRoute.substring(0, oldRoute.indexOf('&search'));
        }
        FormplayerFrontend.navigate(oldRoute + newAddition);
        API.listMenus(appId);
    });


    FormplayerFrontend.on("menu:show:detail", function (model) {
        API.showDetail(model);
    });

    SessionNavigate.on("start", function () {
        new SessionNavigate.Router({
            controller: API,
        });
    });

});