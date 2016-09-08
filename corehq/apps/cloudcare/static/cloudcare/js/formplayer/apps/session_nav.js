/*global FormplayerFrontend, Util */

FormplayerFrontend.module("SessionNavigate", function (SessionNavigate, FormplayerFrontend, Backbone, Marionette) {
    SessionNavigate.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps", // list all apps available to this user
            "single_app/:id": "singleApp", // Show app in phone mode (SingleAppView)
            "sessions": "listSessions", //list all this user's current sessions (incomplete forms)
            "sessions/:id": "getSession",
            ":session": "listMenus",  // Default route
        },
    });

    var API = {
        listApps: function () {
            FormplayerFrontend.trigger("clearForm");
            SessionNavigate.AppList.Controller.listApps();
        },
        singleApp: function(appId) {
            SessionNavigate.AppList.Controller.singleApp(appId);
        },
        selectApp: function (appId) {
            SessionNavigate.MenuList.Controller.selectMenu(appId);
        },
        listMenus: function (sessionObject) {
            FormplayerFrontend.trigger("clearForm");
            var urlObject = Util.CloudcareUrl.fromJson(
                Util.encodedUrlToObject(sessionObject || Backbone.history.getFragment())
            );
            var appId = urlObject.appId;
            var sessionId = urlObject.sessionId;
            var steps = urlObject.steps;
            var page = urlObject.page;
            var search = urlObject.search;
            var queryDict = urlObject.queryDict;
            var previewCommand = urlObject.previewCommand;
            SessionNavigate.MenuList.Controller.selectMenu(
                appId,
                sessionId,
                steps,
                page,
                search,
                queryDict,
                previewCommand
            );
        },
        showDetail: function (model, detailTabIndex) {
            SessionNavigate.MenuList.Controller.showDetail(model, detailTabIndex);
        },
        listSessions: function() {
            FormplayerFrontend.trigger("clearForm");
            SessionNavigate.SessionList.Controller.listSessions();
        },

        getSession: function(sessionId) {
            FormplayerFrontend.request("getSession", sessionId);
        },
        /**
         * renderResponse
         *
         * Takes a response from a successfully submitted form and routes
         * the application to the correct screen. In normal circumstances,
         * the response is a menu response since the user is navigating to
         * module list or home screen. When linking forms, the response will
         * be a form response which will route to a new form.
         */
        renderResponse: function (response) {
            FormplayerFrontend.trigger("clearForm");
            var currentFragment,
                urlObject,
                encodedUrl,
                sessionId,
                menuCollection;

            // Response can be a form response which will result in the the session id
            // being stored in the session_id field. If it's menu response it will be
            // stored in menuSessionId
            sessionId = response.session_id || response.menuSessionId;

            currentFragment = Backbone.history.getFragment();
            urlObject = Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(currentFragment));
            urlObject.setSessionId(sessionId);
            encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
            response.appId = urlObject.appId;
            response.sessionId = sessionId;

            // When the response gets parsed, it will automatically trigger form
            // entry if it is a form response.
            menuCollection = new FormplayerFrontend.Entities.MenuSelectCollection(
                response,
                { parse: true }
            );

            FormplayerFrontend.navigate(encodedUrl);

            SessionNavigate.MenuList.Controller.showMenu(menuCollection);
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
        var urlObject = new Util.CloudcareUrl(appId);
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
    });

    FormplayerFrontend.on("menu:paginate", function (page) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setPage(page);
        Util.setUrlToObject(urlObject);
    });

    FormplayerFrontend.on("menu:search", function (search) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setSearch(search);
        Util.setUrlToObject(urlObject);
    });

    FormplayerFrontend.on("menu:query", function (queryDict) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setQuery(queryDict);
        Util.setUrlToObject(urlObject);
    });

    FormplayerFrontend.on("menu:show:detail", function (model, detailTabIndex) {
        API.showDetail(model, detailTabIndex);
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
        FormplayerFrontend.trigger("clearForm");
        var urlObject = Util.currentUrlToObject();
        urlObject.spliceSteps(index);
        Util.setUrlToObject(urlObject);
        SessionNavigate.MenuList.Controller.selectMenu(urlObject.appId, null, urlObject.steps);
    });


});
