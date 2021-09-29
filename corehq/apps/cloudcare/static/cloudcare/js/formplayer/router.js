/* global Backbone, Marionette */
hqDefine("cloudcare/js/formplayer/router", function () {
    var Util = hqImport("cloudcare/js/formplayer/utils/util");
    var Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps": "listApps", // list all apps available to this user
            "single_app/:id": "singleApp", // Show app in phone mode (SingleAppView)
            "home/:id": "landingPageApp", // Show app in landing page mode (LandingPageAppView)
            "sessions": "listSessions", //list all this user's current sessions (incomplete forms)
            "sessions/:id": "getSession",
            "restore_as/:page/:query": "listUsers",
            "restore_as/:page/": "listUsers",
            "restore_as": "listUsers",
            "settings": "listSettings",
            ":session": "listMenus",  // Default route
        },
    });


    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        appsController = hqImport("cloudcare/js/formplayer/apps/controller"),
        menusController = hqImport("cloudcare/js/formplayer/menus/controller"),
        sessionsController = hqImport("cloudcare/js/formplayer/sessions/controller"),
        usersController = hqImport("cloudcare/js/formplayer/users/controller");
    var API = {
        listApps: function () {
            FormplayerFrontend.regions.getRegion('breadcrumb').empty();
            Util.setStickyQueryInputs({});
            appsController.listApps();
        },
        singleApp: function (appId) {
            var user = FormplayerFrontend.getChannel().request('currentUser');
            FormplayerFrontend.regions.getRegion('breadcrumb').empty();
            user.previewAppId = appId;
            appsController.singleApp(appId);
        },
        landingPageApp: function (appId) {
            appsController.landingPageApp(appId);
        },
        selectApp: function (appId, isInitial) {
            menusController.selectMenu({
                'appId': appId,
                'isInitial': isInitial,
            });
        },
        listMenus: function (sessionObject) {
            var urlObject = Util.CloudcareUrl.fromJson(
                Util.encodedUrlToObject(sessionObject || Backbone.history.getFragment())
            );
            if (!urlObject.appId) {
                // We can't do any menu navigation without an appId
                FormplayerFrontend.trigger("apps:list");
            } else {
                menusController.selectMenu(urlObject);
            }
        },
        listUsers: function (page, query) {
            FormplayerFrontend.trigger("clearForm");
            page = parseInt(page);
            if (_.isNaN(page)) {
                page = 1;
            }
            usersController.listUsers(page, query);
        },
        listSettings: function () {
            appsController.listSettings();
        },
        showDetail: function (caseId, detailTabIndex, isPersistent) {
            menusController.selectDetail(caseId, detailTabIndex, isPersistent);
        },
        listSessions: function (pageNumber, pageSize) {
            sessionsController.listSessions(pageNumber, pageSize);
        },
        getSession: function (sessionId) {
            FormplayerFrontend.getChannel().request("getSession", sessionId);
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
            var currentFragment,
                urlObject,
                encodedUrl,
                menuCollection;

            currentFragment = Backbone.history.getFragment();
            urlObject = Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(currentFragment));
            response.appId = urlObject.appId;

             if (response.notification) {
                FormplayerFrontend.trigger("handleNotification", response.notification);
             }

            // When the response gets parsed, it will automatically trigger form
            // entry if it is a form response.
            menuCollection = hqImport("cloudcare/js/formplayer/menus/collections")(
                response,
                { parse: true }
            );
            // Need to get URL fragment again since fetch might have updated it
            currentFragment = Backbone.history.getFragment();
            urlObject = Util.CloudcareUrl.fromJson(Util.encodedUrlToObject(currentFragment));
            encodedUrl = Util.objectToEncodedUrl(urlObject.toJson());
            FormplayerFrontend.navigate(encodedUrl);

            menusController.showMenu(menuCollection);
        },
    };
    API = hqImport("cloudcare/js/formplayer/middleware").apply(API);

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
        API.selectApp(appId, true);
    });

    FormplayerFrontend.on('app:singleApp', function (appId) {
        FormplayerFrontend.navigate("/single_app/" + appId);
        API.singleApp(appId);
    });

    FormplayerFrontend.on('app:landingPageApp', function (appId) {
        FormplayerFrontend.navigate("/home/" + appId);
        API.landingPageApp(appId);
    });

    FormplayerFrontend.on("menu:select", function (index, smartLinkTemplate) {
        var urlObject = Util.currentUrlToObject();
        if (index === undefined) {
            urlObject.setQueryData(undefined, false);
            urlObject.setForceManualAction(true);
        } else {
            urlObject.addSelection(index);
            urlObject.setForceManualAction(false);
        }
        if (smartLinkTemplate) {
            urlObject.setSmartLinkTemplate(smartLinkTemplate);
        }
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:paginate", function (page) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setPage(page);
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:perPageLimit", function (casesPerPage) {
        var urlObject = Util.currentUrlToObject();
        urlObject.setCasesPerPage(casesPerPage);
        Util.setUrlToObject(urlObject);
        Util.savePerPageLimitCookie('cases', casesPerPage);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:sort", function (newSortIndex) {
        var urlObject = Util.currentUrlToObject();
        var currentSortIndex = urlObject.sortIndex;
        // If the column index is the same as already loaded, reverse the sort
        if (newSortIndex === Math.abs(currentSortIndex)) {
            newSortIndex = -1 * currentSortIndex;
        }
        urlObject.setSort(newSortIndex);
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
        urlObject.setQueryData(queryDict, true);
        Util.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on('restore_as:list', function () {
        FormplayerFrontend.navigate("/restore_as");
        API.listUsers();
    });

    FormplayerFrontend.on('settings:list', function () {
        FormplayerFrontend.navigate("/settings");
        API.listSettings();
    });

    FormplayerFrontend.on("menu:show:detail", function (caseId, detailTabIndex, isPersistent) {
        API.showDetail(caseId, detailTabIndex, isPersistent);
    });

    FormplayerFrontend.on("sessions", function (pageNumber, pageSize) {
        FormplayerFrontend.navigate("/sessions", pageNumber, pageSize);
        API.listSessions(pageNumber, pageSize);
    });

    FormplayerFrontend.on("getSession", function (sessionId) {
        FormplayerFrontend.navigate("/sessions/" + sessionId);
        API.getSession(sessionId);
    });

    FormplayerFrontend.on("renderResponse", function (menuResponse) {
        API.renderResponse(menuResponse);
    });

    FormplayerFrontend.on("breadcrumbSelect", function (index) {
        FormplayerFrontend.trigger("clearForm");
        var urlObject = Util.currentUrlToObject();
        urlObject.spliceSelections(index);
        Util.setUrlToObject(urlObject);
        var options = {
            'appId': urlObject.appId,
            'selections': urlObject.selections,
            'queryData': urlObject.queryData,
        };
        hqImport("cloudcare/js/formplayer/menus/controller").selectMenu(options);
    });

    return {
        start: function () {
            return new Router({
                controller: API,
            });
        },
    };
});
