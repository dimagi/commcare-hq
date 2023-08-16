/* global Backbone, Marionette */
hqDefine("cloudcare/js/formplayer/router", function () {
    var utils = hqImport("cloudcare/js/formplayer/utils/utils");
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
        Middleware = hqImport("cloudcare/js/formplayer/middleware"),
        appsController = hqImport("cloudcare/js/formplayer/apps/controller"),
        menusCollections = hqImport("cloudcare/js/formplayer/menus/collections"),
        menusController = hqImport("cloudcare/js/formplayer/menus/controller"),
        sessionsController = hqImport("cloudcare/js/formplayer/sessions/controller"),
        usersController = hqImport("cloudcare/js/formplayer/users/controller");
    var API = {
        listApps: function () {
            FormplayerFrontend.regions.getRegion('breadcrumb').empty();
            utils.setStickyQueryInputs({});
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
            var urlObject = utils.CloudcareUrl.fromJson(
                utils.encodedUrlToObject(sessionObject || Backbone.history.getFragment())
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
        showDetail: function (caseId, detailTabIndex, isPersistent, isMultiSelect) {
            menusController.selectDetail(caseId, detailTabIndex, isPersistent, isMultiSelect);
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
            urlObject = utils.CloudcareUrl.fromJson(utils.encodedUrlToObject(currentFragment));
            if (urlObject.appId) {
                // will be undefined on urlObject when coming from an incomplete form
                response.appId = urlObject.appId;
            }

             if (response.notification) {
                FormplayerFrontend.trigger("handleNotification", response.notification);
             }

            // When the response gets parsed, it will automatically trigger form
            // entry if it is a form response.
            menuCollection = menusCollections(
                response,
                { parse: true }
            );
            // Need to get URL fragment again since fetch might have updated it
            currentFragment = Backbone.history.getFragment();
            urlObject = utils.CloudcareUrl.fromJson(utils.encodedUrlToObject(currentFragment));
            encodedUrl = utils.objectToEncodedUrl(urlObject.toJson());
            FormplayerFrontend.navigate(encodedUrl);

            menusController.showMenu(menuCollection);
        },
    };
    API = Middleware.apply(API);

    FormplayerFrontend.on("apps:currentApp", function () {
        var urlObject = utils.currentUrlToObject();
        urlObject.clearExceptApp();
        utils.setUrlToObject(urlObject, true);
        API.selectApp(urlObject.appId);
    });

    FormplayerFrontend.on("apps:list", function () {
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function (appId) {
        var urlObject = new utils.CloudcareUrl({'appId': appId});
        utils.setUrlToObject(urlObject);
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

    FormplayerFrontend.on("menu:select", function (index) {
        var urlObject = utils.currentUrlToObject();
        if (index === undefined) {
            urlObject.setQueryData({
                inputs: null,
                execute: false,
                forceManualSearch: true,
            });
        } else {
            urlObject.addSelection(index);
            FormplayerFrontend.regions.getRegion('sidebar').empty();
        }
        utils.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:paginate", function (page, selections) {
        var urlObject = utils.currentUrlToObject();
        urlObject.setPage(page);
        utils.setSelectedValues(selections);
        utils.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:perPageLimit", function (casesPerPage, selections) {
        var urlObject = utils.currentUrlToObject();
        urlObject.setCasesPerPage(casesPerPage);
        utils.setSelectedValues(selections);
        utils.setUrlToObject(urlObject);
        utils.savePerPageLimitCookie('cases', casesPerPage);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:sort", function (newSortIndex) {
        var urlObject = utils.currentUrlToObject();
        var currentSortIndex = urlObject.sortIndex;
        // If the column index is the same as already loaded, reverse the sort
        if (newSortIndex === Math.abs(currentSortIndex)) {
            newSortIndex = -1 * currentSortIndex;
        }
        urlObject.setSort(newSortIndex);
        utils.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:search", function (search) {
        var urlObject = utils.currentUrlToObject();
        urlObject.setSearch(search);
        utils.setUrlToObject(urlObject);
        API.listMenus();
    });

    FormplayerFrontend.on("menu:query", function (queryDict, selectValuesByKeys = false, sidebarEnabled) {
        var urlObject = utils.currentUrlToObject();
        var queryObject = _.extend(
            {
                inputs: queryDict,
                execute: true,
                selectValuesByKeys,
            },
            // force manual search in split screen case search for workflow compatibility
            sidebarEnabled ? { forceManualSearch: true } : {}
        );
        urlObject.setQueryData(queryObject);
        utils.setUrlToObject(urlObject);
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

    FormplayerFrontend.on("menu:show:detail", function (caseId, detailTabIndex, isMultiSelect, isPersistent) {
        API.showDetail(caseId, detailTabIndex, isPersistent, isMultiSelect);
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
        var urlObject = utils.currentUrlToObject();
        urlObject.spliceSelections(index);
        utils.setUrlToObject(urlObject);
        var options = {
            'appId': urlObject.appId,
            'selections': urlObject.selections,
            'queryData': urlObject.queryData,
        };
        menusController.selectMenu(options);
    });

    return {
        start: function () {
            return new Router({
                controller: API,
            });
        },
    };
});
