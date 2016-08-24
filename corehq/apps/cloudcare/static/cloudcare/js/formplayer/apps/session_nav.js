/*global FormplayerFrontend, Util */

FormplayerFrontend.module("SessionNavigate", function (SessionNavigate, FormplayerFrontend, Backbone, Marionette) {
    SessionNavigate.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps", // list all apps available to this user
            "single_app/:id": "singleApp", // Show app in phone mode (SingleAppView)
            "sessions": "listSessions", //list all this user's current sessions (incomplete forms)
            "sessions/:id": "getSession",
            "local/:path": "localInstall",
            ":session": "listMenus",  // Default route
        },
    });

    var API = {
        listApps: function () {
            FormplayerFrontend.request("clearForm");
            SessionNavigate.AppList.Controller.listApps();
        },
        singleApp: function(appId) {
            SessionNavigate.AppList.Controller.singleApp(appId);
        },
        selectApp: function (appId) {
            SessionNavigate.MenuList.Controller.selectMenu({
                'appId': appId,
            });
        },
        listMenus: function (sessionObject) {
            FormplayerFrontend.request("clearForm");
            var urlObject = Util.CloudcareUrl.fromJson(
                Util.encodedUrlToObject(sessionObject || Backbone.history.getFragment())
            );
            SessionNavigate.MenuList.Controller.selectMenu(urlObject);
        },
        showDetail: function (model, index) {
            SessionNavigate.MenuList.Controller.showDetail(model, index);
        },
        listSessions: function() {
            FormplayerFrontend.request("clearForm");
            SessionNavigate.SessionList.Controller.listSessions();
        },
        getSession: function(sessionId) {
            FormplayerFrontend.request("getSession", sessionId);
        },
        localInstall: function(path) {
            FormplayerFrontend.trigger("localInstall", path);
        },
        renderResponse: function (menuResponse) {
            FormplayerFrontend.request("clearForm");
            var NextScreenCollection = Backbone.Collection.extend({});
            var nextScreenCollection;
            //TODO: clean up this hackiness
            if (menuResponse.commands) {
                nextScreenCollection = new NextScreenCollection(menuResponse.commands);
                nextScreenCollection.type = "commands";
            } else {
                nextScreenCollection = new NextScreenCollection(menuResponse.entities);
                nextScreenCollection.type = "entities";
            }
            nextScreenCollection.title = menuResponse.title;
            nextScreenCollection.locales = menuResponse.locales;
            nextScreenCollection.sessionId = menuResponse.menuSessionId;
            nextScreenCollection.headers = menuResponse.headers;
            nextScreenCollection.styles = menuResponse.styles;
            nextScreenCollection.tiles = menuResponse.tiles;
            nextScreenCollection.action = menuResponse.action;
            nextScreenCollection.breadcrumbs = menuResponse.breadcrumbs;
            var currentFragment = Backbone.history.getFragment();
            var urlObject = Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(currentFragment));
            urlObject.setSessionId(nextScreenCollection.sessionId);
            var encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
            FormplayerFrontend.navigate(encodedUrl);
            SessionNavigate.MenuList.Controller.showMenu(nextScreenCollection);
        },
    };

    FormplayerFrontend.on("apps:currentApp", function () {
        var urlObject = Util.currentUrlToObject();
        urlObject.clearExceptApp();
        Util.setUrlToObject(urlObject);
        API.selectApp(urlObject.appId);
    });

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (appId) {
        var urlObject = new Util.CloudcareUrl({'appId': appId});
        Util.setUrlToObject(urlObject);
        API.selectApp(appId);
    });

    FormplayerFrontend.on('app:singleApp', function(appId) {
        FormplayerFrontend.navigate("/single_app/" + appId);
        API.singleApp(appId);
    });

    FormplayerFrontend.on("menu:select", function (index) {
        var urlObject = Util.currentUrlToObject();
        urlObject.addStep(index);
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:paginate", function (page) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setPage(page);
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:search", function (search) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setSearch(search);
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:query", function (queryDict) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setQuery(queryDict);
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:show:detail", function (model, index) {
        API.showDetail(model, index);
    });

    FormplayerFrontend.on("sessions", function () {
        FormplayerFrontend.navigate("/sessions");
        API.listSessions();
    });

    FormplayerFrontend.on("getSession", function (sessionId) {
        FormplayerFrontend.navigate("/sessions/" + sessionId);
        API.getSession(sessionId);
    });

    FormplayerFrontend.on("renderResponse", function (menuResponse) {
        API.renderResponse(menuResponse);
    });

    SessionNavigate.on("start", function () {
        new SessionNavigate.Router({
            controller: API,
        });
    });

    FormplayerFrontend.on("breadcrumbSelect", function (index) {
        FormplayerFrontend.request("clearForm");
        var urlObject = Util.currentUrlToObject();
        urlObject.spliceSteps(index);
        Util.setUrlToObject(urlObject);
        var options = {
            'appId': urlObject.appId,
            'steps': urlObject.steps,
        }
        SessionNavigate.MenuList.Controller.selectMenu(options);
    });


    FormplayerFrontend.on("localInstall", function (path) {
        var urlObject = new Util.CloudcareUrl({
            'installReference': path,
        });
        Util.setUrlToObject(urlObject);
        SessionNavigate.MenuList.Controller.selectMenu(urlObject);
    });
});
