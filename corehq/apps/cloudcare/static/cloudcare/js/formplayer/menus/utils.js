/*global Backbone */

hqDefine("cloudcare/js/formplayer/menus/utils", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        kissmetrics = hqImport("analytix/js/kissmetrix"),
        ProgressBar = hqImport("cloudcare/js/formplayer/layout/views/progress_bar"),
        QueryView = hqImport("cloudcare/js/formplayer/menus/views/query"),
        toggles = hqImport("hqwebapp/js/toggles"),
        utils = hqImport("cloudcare/js/formplayer/utils/utils"),
        views = hqImport("cloudcare/js/formplayer/menus/views");

    var recordPosition = function (position) {
        sessionStorage.locationLat = position.coords.latitude;
        sessionStorage.locationLon = position.coords.longitude;
        sessionStorage.locationAltitude = position.coords.altitude;
        sessionStorage.locationAccuracy = position.coords.accuracy;
    };

    var handleLocationRequest = function (optionsFromLastRequest) {
        var success = function (position) {
            hqRequire(["cloudcare/js/formplayer/menus/controller"], function (MenusController) {
                FormplayerFrontend.regions.getRegion('loadingProgress').empty();
                recordPosition(position);
                MenusController.selectMenu(optionsFromLastRequest);
            });
        };

        var error = function (err) {
            FormplayerFrontend.regions.getRegion('loadingProgress').empty();
            FormplayerFrontend.trigger('showError',
                getErrorMessage(err) +
                "Without access to your location, computations that rely on the here() function will show up blank.",
                false, false
            );
        };

        var getErrorMessage = function (err) {
            switch (err.code) {
                case err.PERMISSION_DENIED:
                    return "You denied CommCare HQ permission to read your browser's current location. ";
                case err.TIMEOUT:
                    return "Your connection was not strong enough to acquire your location. Please try again later. ";
                case err.POSITION_UNAVAILABLE:
                default:
                    return "Your browser location could not be determined. ";
            }
        };

        if (navigator.geolocation) {
            var progressView = ProgressBar({
                progressMessage: gettext("Fetching your location..."),
            });
            FormplayerFrontend.regions.getRegion('loadingProgress').show(progressView.render());
            navigator.geolocation.getCurrentPosition(success, error, {timeout: 10000});
        }
    };

    var startOrStopLocationWatching = function (shouldWatchLocation) {
        if (navigator.geolocation) {
            var watching = Boolean(sessionStorage.lastLocationWatchId);
            if (!watching && shouldWatchLocation) {
                sessionStorage.lastLocationWatchId = navigator.geolocation.watchPosition(recordPosition);
            } else if (watching && !shouldWatchLocation) {
                navigator.geolocation.clearWatch(sessionStorage.lastLocationWatchId);
                sessionStorage.lastLocationWatchId = '';
            }
        }
    };

    var showBreadcrumbs = function (breadcrumbs) {
        var detailCollection,
            breadcrumbModels;

        breadcrumbModels = _.map(breadcrumbs, function (breadcrumb, idx) {
            return {
                data: breadcrumb,
                id: idx,
            };
        });

        detailCollection = new Backbone.Collection(breadcrumbModels);
        var breadcrumbView = views.BreadcrumbListView({
            collection: detailCollection,
        });
        FormplayerFrontend.regions.getRegion('breadcrumb').show(breadcrumbView);
    };

    var showFormMenu = function (langs, enableLanguageMenu) {
        var langModels,
            langCollection;

        FormplayerFrontend.regions.addRegions({
            formMenu: "#form-menu",
        });
        if (langs && enableLanguageMenu) {
            langModels = _.map(langs, function (lang) {
                return {
                    lang: lang,
                };
            });
            langCollection = new Backbone.Collection(langModels);
        } else {
            langCollection = null;
        }
        var formMenuView = views.FormMenuView({
            collection: langCollection,
        });
        FormplayerFrontend.regions.getRegion('formMenu').show(formMenuView);
    };

    var getMenuData = function (menuResponse) {
        return {                    // TODO: make this more concise
            collection: menuResponse,
            title: menuResponse.title,
            headers: menuResponse.headers,
            widthHints: menuResponse.widthHints,
            actions: menuResponse.actions,
            pageCount: menuResponse.pageCount,
            currentPage: menuResponse.currentPage,
            styles: menuResponse.styles,
            type: menuResponse.type,
            sessionId: menuResponse.sessionId,
            tiles: menuResponse.tiles,
            numEntitiesPerRow: menuResponse.numEntitiesPerRow,
            maxHeight: menuResponse.maxHeight,
            maxWidth: menuResponse.maxWidth,
            redoLast: menuResponse.redoLast,
            useUniformUnits: menuResponse.useUniformUnits,
            isPersistentDetail: menuResponse.isPersistentDetail,
            sortIndices: menuResponse.sortIndices,
            isMultiSelect: menuResponse.multiSelect,
            multiSelectMaxSelectValue: menuResponse.maxSelectValue,
        }
    };

    var getCaseListView = function(menuResponse) {
        if (menuResponse.tiles === null || menuResponse.tiles === undefined) {
            if (menuResponse.multiSelect) {
                return views.MultiSelectCaseListView;
            } else {
                return views.CaseListView;
            }
        } else {
            if (menuResponse.groupHeaderRows >= 0) {
                return views.CaseTileGroupedListView;
            } else {
                return views.CaseTileListView;
            }
        }
    }

    var getMenuView = function (menuResponse) {
        var menuData = getMenuData(menuResponse);
        var urlObject = utils.currentUrlToObject();

        sessionStorage.queryKey = menuResponse.queryKey;
        if (menuResponse.type === "commands") {
            return views.MenuListView(menuData);
        } else if (menuResponse.type === "query") {
            var props = {
                domain: FormplayerFrontend.getChannel().request('currentUser').domain,
            };
            if (menuResponse.breadcrumbs && menuResponse.breadcrumbs.length) {
                props.name = menuResponse.breadcrumbs[menuResponse.breadcrumbs.length - 1];
            }
            kissmetrics.track.event('Case Search', props);
            urlObject.setQueryData({
                inputs: {},
                execute: false,
                forceManualSearch: false,
            });
            return QueryView(menuData);
        } else if (menuResponse.type === "entities") {
            var searchText = urlObject.search;
            var event = "Viewed Case List";
            if (searchText) {
                event = "Searched Case List";
            }
            if (menuResponse.queryResponse != null) {
                menuData.sidebarEnabled = true;
            }
            var eventData = {
                domain: FormplayerFrontend.getChannel().request("currentUser").domain,
                name: menuResponse.title,
            };
            var fields = _.pick(utils.getCurrentQueryInputs(), function (v) { return !!v; });
            if (!_.isEmpty(fields)) {
                eventData.searchFields = _.sortBy(_.keys(fields)).join(",");
            }
            kissmetrics.track.event(event, eventData);
            if (/search_command\.m\d+/.test(menuResponse.queryKey) && menuResponse.currentPage === 0) {
                kissmetrics.track.event('Started Case Search', {
                    'Split Screen Case Search': toggles.toggleEnabled('SPLIT_SCREEN_CASE_SEARCH'),
                });
            }
            var caseListView = getCaseListView(menuResponse);
            return caseListView(menuData);
        }
    };

    return {
        getMenuView: getMenuView,
        getMenuData: getMenuData,
        getCaseListView: getCaseListView,
        handleLocationRequest: handleLocationRequest,
        showBreadcrumbs: showBreadcrumbs,
        showFormMenu: showFormMenu,
        startOrStopLocationWatching: startOrStopLocationWatching,
    };
});
