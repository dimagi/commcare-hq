/*global FormplayerFrontend, Util */

FormplayerFrontend.module("SessionNavigate", function (SessionNavigate, FormplayerFrontend, Backbone, Marionette) {
    SessionNavigate.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps", // list all apps available to this user
            "apps/:id": "selectApp", // select the app under :id and list root commands
            "apps/:id/menu": "listMenus", // select the app under :id, make session steps in params, display screen
            "apps/sessions": "listSessions", //list all this user's current sessions (incomplete forms)
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
            if (steps && steps.length > 0) {
                SessionNavigate.MenuList.Controller.selectMenu(appId, steps, page);
            } else {
                SessionNavigate.MenuList.Controller.selectMenu(appId);
            }
        },
        showDetail: function (model) {
            SessionNavigate.MenuList.Controller.showDetail(model);
        },
        listSessions: function() {
            SessionNavigate.SessionList.Controller.listSessions();
        },

        getIncompleteForm: function(sessionId) {
            FormplayerFrontend.request("getIncompleteForm", sessionId);
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
        if (oldRoute.indexOf('page') > 0) {
            oldRoute = oldRoute.substring(0, oldRoute.indexOf('&page'));
        }
        FormplayerFrontend.navigate(oldRoute + newAddition);
        API.listMenus(appId);
    });

    FormplayerFrontend.on("menu:show:detail", function (model) {
        API.showDetail(model);
    });

    FormplayerFrontend.on("sessions", function () {
        API.listSessions();
    });

    FormplayerFrontend.on("getIncompleteForm", function (sessionId) {
        API.getIncompleteForm(sessionId);
    });

    SessionNavigate.on("start", function () {
        new SessionNavigate.Router({
            controller: API,
        });
    });

});