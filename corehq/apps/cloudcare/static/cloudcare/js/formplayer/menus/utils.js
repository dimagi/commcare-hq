import _ from "underscore";
import Backbone from "backbone";
import toggles from "hqwebapp/js/toggles";
import noopMetrics from "analytix/js/noopMetrics";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import constants from "cloudcare/js/formplayer/constants";
import view from "cloudcare/js/formplayer/menus/views/query";
import UsersModels from "cloudcare/js/formplayer/users/models";
import utils from "cloudcare/js/formplayer/utils/utils";
import views from "cloudcare/js/formplayer/menus/views";
import gtx from "cloudcare/js/gtx";

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
    if (detailCollection.length) {
        detailCollection.last().set('ariaCurrentPage', true);
    }
    var breadcrumbView = views.BreadcrumbListView({
        collection: detailCollection,
    });
    FormplayerFrontend.regions.getRegion('breadcrumb').show(breadcrumbView);
};

var showMenuDropdown = function (langs, langCodeNameMapping) {
    let langModels,
        langCollection;

    FormplayerFrontend.regions.addRegions({
        breadcrumbMenuDropdown: "#navbar-menu-region",
    });

    if (langs && langs.length > 1) {
        langModels = _.map(langs, function (lang) {
            let matchingLanguage = langCodeNameMapping[lang];
            return {
                lang_code: lang,
                lang_label: matchingLanguage ? matchingLanguage : lang,
            };
        });
        langCollection = new Backbone.Collection(langModels);
    } else {
        langCollection = null;
    }
    let menuDropdownView = views.MenuDropdownView({
        collection: langCollection,
    });
    FormplayerFrontend.regions.getRegion('breadcrumbMenuDropdown').show(menuDropdownView);
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
        dynamicSearch: menuResponse.dynamicSearch,
        endpointActions: menuResponse.endpointActions,
        groupHeaders: menuResponse.groupHeaders,
    };
};

var getCaseListView = function (menuResponse) {
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
};

var isSidebarEnabled = function (menuResponse) {
    if (menuResponse.type === constants.QUERY) {
        return menuResponse.models && menuResponse.models.length > 0;
    } else if (menuResponse.type === constants.ENTITIES) {
        return menuResponse.queryResponse && menuResponse.queryResponse.displays.length > 0;
    }
};

var getMenuView = function (menuResponse) {
    var menuData = getMenuData(menuResponse);
    var urlObject = utils.currentUrlToObject();

    sessionStorage.queryKey = menuResponse.queryKey;
    if (menuResponse.type === "commands") {
        return views.MenuListView(menuData);
    } else if (menuResponse.type === constants.QUERY) {
        var props = {
            domain: UsersModels.getCurrentUser().domain,
        };
        if (menuResponse.breadcrumbs && menuResponse.breadcrumbs.length) {
            props.name = menuResponse.breadcrumbs[menuResponse.breadcrumbs.length - 1];
        }
        noopMetrics.track.event('Case Search', props);
        urlObject.setQueryData({
            inputs: {},
            execute: false,
            forceManualSearch: false,
        });
        return view.queryListView(menuData);
    } else if (menuResponse.type === constants.ENTITIES) {

        if (isSidebarEnabled(menuResponse)) {
            menuData.sidebarEnabled = true;
        }
        var eventData = {};
        var fields = _.pick(utils.getCurrentQueryInputs(), function (v) { return !!v; });
        var searchFieldList = [];
        if (!_.isEmpty(fields)) {
            searchFieldList = _.sortBy(_.keys(fields));
            eventData.searchFields = searchFieldList.join(",");
        }

        noopMetrics.track.event("Viewed Case List", _.extend(eventData, {
            domain: UsersModels.getCurrentUser().domain,
            name: menuResponse.title,
        }));
        gtx.logCaseList(menuResponse, searchFieldList);

        if (/search_command\.m\d+/.test(menuResponse.queryKey) && menuResponse.currentPage === 0) {
            noopMetrics.track.event('Started Case Search', {
                'Split Screen Case Search': true,  // Always enabled: split screen is always on for case search.
            });
        }
        var caseListView = getCaseListView(menuResponse);
        return caseListView(menuData);
    }
};

export default {
    getMenuView: getMenuView,
    getMenuData: getMenuData,
    getCaseListView: getCaseListView,
    showBreadcrumbs: showBreadcrumbs,
    showMenuDropdown: showMenuDropdown,
    isSidebarEnabled: isSidebarEnabled,
};
