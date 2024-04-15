'use strict';
hqDefine("cloudcare/js/formplayer/menus/controller", [
    'jquery',
    'underscore',
    'backbone',
    'DOMPurify/dist/purify.min',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    'cloudcare/js/markdown',
    'cloudcare/js/formplayer/constants',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/users/models',
    'cloudcare/js/formplayer/utils/utils',
    'cloudcare/js/formplayer/menus/collections',
    'cloudcare/js/formplayer/menus/utils',
    'cloudcare/js/formplayer/menus/views/query',
    'cloudcare/js/formplayer/menus/views',
    'cloudcare/js/formplayer/menus/api',    // app:select:menus and entity:get:details
], function (
    $,
    _,
    Backbone,
    DOMPurify,
    initialPageData,
    toggles,
    markdown,
    constants,
    FormplayerFrontend,
    UsersModels,
    formplayerUtils,
    Collection,
    menusUtils,
    queryView,
    views
) {
    var selectMenu = function (options) {

        options.preview = UsersModels.getCurrentUser().displayOptions.singleAppMode;

        var fetchingNextMenu = FormplayerFrontend.getChannel().request("app:select:menus", options);

        /*
         Determine the next screen to display.  Could be
         a list of commands (modules and/or forms)
         a list of entities (cases) and their details
         */
        $.when(fetchingNextMenu).done(function (menuResponse) {
            if (menuResponse.abort) {
                return;
            }

            //set title of tab to application name
            if (menuResponse.breadcrumbs) {
                document.title = menuResponse.breadcrumbs[0];
            }

            // show any notifications from Formplayer
            if (menuResponse.notification && !_.isNull(menuResponse.notification.message)) {
                FormplayerFrontend.trigger("handleNotification", menuResponse.notification);
            }

            // If redirect was set, clear and go home.
            if (menuResponse.clearSession) {
                FormplayerFrontend.trigger("apps:currentApp");
                return;
            }

            var urlObject = formplayerUtils.currentUrlToObject();
            if (urlObject.endpointId) {
                menuResponse.breadcrumbs = [];
                urlObject.replaceEndpoint(menuResponse.selections);
                formplayerUtils.setUrlToObject(urlObject);
            }

            formplayerUtils.doUrlAction((urlObject) => {
                let updated = false;
                if (menuResponse.session_id) {
                    urlObject.sessionId = menuResponse.session_id;
                    updated = true;
                } else if (urlObject.sessionId) {
                    urlObject.sessionId = null;
                    updated = true;
                }
                return updated;
            }, true);


            // If we don't have an appId in the URL (usually due to form preview)
            // then parse the appId from the response.
            if (urlObject.appId === undefined || urlObject.appId === null) {
                if (menuResponse.appId === null || menuResponse.appId === undefined) {
                    FormplayerFrontend.trigger('showError', "Response did not contain appId even though it was" +
                        "required. If this persists, please report an issue to CommCare HQ");
                    FormplayerFrontend.trigger("apps:list");
                    return;
                }
                urlObject.appId = menuResponse.appId;
                formplayerUtils.setUrlToObject(urlObject);
            }

            showMenu(menuResponse);
            // If a search exists in urlObject, make set search bar continues to show search
            if (urlObject.search !== null) {
                $('#searchText').val(urlObject.search);
            }

            if (menuResponse.shouldRequestLocation) {
                menusUtils.handleLocationRequest(options);
            }
            menusUtils.startOrStopLocationWatching(menuResponse.shouldWatchLocation);
        }).fail(function () {
            //  if it didn't go through, then it displayed an error message.
            // the right thing to do is then to just stay in the same place.
        });
    };

    var selectDetail = function (caseId, detailIndex, isPersistent, isMultiSelect) {
        var urlObject = formplayerUtils.currentUrlToObject();
        if (!isPersistent) {
            urlObject.addSelection(caseId);
        }
        var fetchingDetails = FormplayerFrontend.getChannel().request("entity:get:details", urlObject, isPersistent, false);
        $.when(fetchingDetails).done(function (detailResponse) {
            showDetail(detailResponse, detailIndex, caseId, isMultiSelect);
        }).fail(function () {
            FormplayerFrontend.trigger('navigateHome');
        });
    };

    var showMenu = function (menuResponse) {
        var menuListView = menusUtils.getMenuView(menuResponse);
        var appPreview = UsersModels.getCurrentUser().displayOptions.singleAppMode;
        var sidebarEnabled = !appPreview && menusUtils.isSidebarEnabled(menuResponse);
        if (menuListView && !sidebarEnabled) {
            FormplayerFrontend.regions.getRegion('main').show(menuListView);
        }
        if (sidebarEnabled) {
            showSplitScreenQuery(menuResponse, menuListView);
        } else {
            FormplayerFrontend.regions.getRegion('sidebar').empty();
        }
        if (menuResponse.persistentCaseTile && !appPreview) {
            showPersistentCaseTile(menuResponse.persistentCaseTile);
        } else {
            FormplayerFrontend.regions.getRegion('persistentCaseTile').empty();
        }

        if (menuResponse.breadcrumbs) {
            menusUtils.showBreadcrumbs(menuResponse.breadcrumbs);
            if (!appPreview) {
                let isFormEntry = !menuResponse.queryKey;
                if (isFormEntry) {
                    menusUtils.showMenuDropdown(menuResponse.langs, initialPageData.get('lang_code_name_mapping'));
                }
                if (menuResponse.type === constants.ENTITIES) {
                    menusUtils.showMenuDropdown();
                }
            }
        } else {
            FormplayerFrontend.regions.getRegion('breadcrumb').empty();
        }
        if (menuResponse.appVersion) {
            FormplayerFrontend.trigger('setVersionInfo', menuResponse.appVersion);
        }
    };

    var showSplitScreenQuery = function (menuResponse, menuListView) {
        var menuData = menusUtils.getMenuData(menuResponse);
        var queryResponse = menuResponse.queryResponse;
        if (menuResponse.type === constants.ENTITIES && queryResponse)  {
            var queryCollection = new Collection(queryResponse.displays);
            FormplayerFrontend.regions.getRegion('sidebar').show(
                queryView.queryListView({
                    collection: queryCollection,
                    title: menuResponse.title,
                    description: menuResponse.description,
                    hasDynamicSearch: queryResponse.dynamicSearch,
                    sidebarEnabled: true,
                    disableDynamicSearch: !sessionStorage.submitPerformed,
                    groupHeaders: queryResponse.groupHeaders,
                    searchOnClear: queryResponse.searchOnClear,
                }).render()
            );
            FormplayerFrontend.regions.getRegion('main').show(menuListView);
        } else if (menuResponse.type === constants.QUERY) {
            FormplayerFrontend.regions.getRegion('sidebar').show(
                queryView.queryListView({
                    collection: menuResponse,
                    title: menuResponse.title,
                    description: menuResponse.description,
                    hasDynamicSearch: menuResponse.dynamicSearch,
                    sidebarEnabled: true,
                    disableDynamicSearch: true,
                    groupHeaders: menuResponse.groupHeaders,
                    searchOnClear: menuResponse.searchOnClear,
                }).render()
            );

            menuData["triggerEmptyCaseList"] = true;
            menuData["sidebarEnabled"] = true;
            menuData["description"] = menuResponse.description;

            var caseListView = menusUtils.getCaseListView(menuResponse);
            FormplayerFrontend.regions.getRegion('main').show(caseListView(menuData));
        }
    };

    var showPersistentCaseTile = function (persistentCaseTile) {
        var detailView = getCaseTile(persistentCaseTile);
        FormplayerFrontend.regions.getRegion('persistentCaseTile').show(detailView.render());
    };

    var showDetail = function (model, detailTabIndex, caseId, isMultiSelect) {
        var detailObjects = model.filter(function (d) {
            const styles = d.get('styles');
            const visibleStyle = _.find(styles, s => s.displayFormat !== constants.FORMAT_ADDRESS_POPUP);
            return typeof visibleStyle !== 'undefined';
        });

        // If we have no details, just select the entity
        if (detailObjects === null || detailObjects === undefined || detailObjects.length === 0) {
            if (isMultiSelect) {
                FormplayerFrontend.trigger("multiSelect:updateCases", constants.MULTI_SELECT_ADD, [caseId]);
            } else {
                FormplayerFrontend.trigger("menu:select", caseId);
            }
            return;
        }
        var tabModels = _.map(detailObjects, function (detail, index) {
            return {title: detail.get('title'), id: index, active: index === detailTabIndex};
        });
        var tabCollection = new Backbone.Collection();
        tabCollection.reset(tabModels);

        let contentView;
        const detailObject = detailObjects[detailTabIndex],
            usesCaseTiles = detailObject.get('usesCaseTiles');
        if (usesCaseTiles && !detailObject.get('entities')) {
            contentView = getCaseTile(detailObject.toJSON());
        } else {
            contentView = getDetailList(detailObject);
        }

        var tabListView = views.DetailTabListView({
            collection: tabCollection,
            onTabClick: function (detailTabIndex) {
                showDetail(model, detailTabIndex, caseId, isMultiSelect);
            },
        });
        var detailFooterView = views.CaseDetailFooterView({
            model: model,
            caseId: caseId,
            isMultiSelect: isMultiSelect,
        });
        $('#case-detail-modal').find('.js-detail-tabs').html(tabListView.render().el);
        $('#case-detail-modal').find('.js-detail-content').html(contentView.render().el);
        $('#case-detail-modal').find('.js-detail-footer-content').html(detailFooterView.render().el);
        $('#case-detail-modal').modal('show');

    };

    var getDetailList = function (detailObject) {
        var i;
        if (detailObject.get('entities')) {
            // This is a data tab, displaying a table
            var entities = detailObject.get('entities');
            var listModel = [];
            // we need to map the details and headers JSON to a list for a Backbone Collection
            for (i = 0; i < entities.length; i++) {
                var listObj = {};
                listObj.data = entities[i].data;
                listObj.id = i;
                listModel.push(listObj);
            }
            var listCollection = new Backbone.Collection();
            listCollection.reset(listModel);
            var menuData = {
                collection: listCollection,
                headers: detailObject.get('headers'),
                styles: detailObject.get('styles'),
                tiles: detailObject.get('tiles'),
                title: detailObject.get('title'),
            };
            if (detailObject.get('usesCaseTiles')) {
                return views.CaseTileDetailView(menuData);
            }
            return views.CaseListDetailView(menuData);
        }

        // This is a regular detail, displaying name-value pairs
        var headers = detailObject.get('headers');
        var details = detailObject.get('details');
        var styles = detailObject.get('styles');
        var altText = detailObject.get('altText');
        var detailModel = [];
        // we need to map the details and headers JSON to a list for a Backbone Collection
        for (i = 0; i < headers.length; i++) {
            var obj = {};
            obj.data = details[i];
            obj.header = headers[i];
            obj.style = styles[i];
            obj.altText = altText[i];
            obj.id = i;
            if (obj.style.displayFormat === constants.FORMAT_MARKDOWN) {
                obj.html = markdown.render(details[i]);
            }
            if (obj.style.displayFormat !== constants.FORMAT_ADDRESS_POPUP) {
                detailModel.push(obj);
            }
        }
        var detailCollection = new Backbone.Collection();
        detailCollection.reset(detailModel);
        return views.DetailListView({
            collection: detailCollection,
        });
    };

    const onlyVisibleColumns = function (detailObject) {
        const indices = _.chain(detailObject.styles)
            .map((value, index) => [value, index])
            .filter(([s]) => s.displayFormat !== constants.FORMAT_ADDRESS_POPUP)
            .map(([, index]) => index)
            .value();

        return {
            styles: _.map(indices, index => detailObject.styles[index]),
            altText: _.map(indices, index => detailObject.altText[index]),
            tiles: _.map(indices, index => detailObject.tiles[index]),
            details: _.map(indices, index => detailObject.details[index]),
        };
    };

    // return a case tile from a detail object (for persistent case tile and case tile in case detail)
    var getCaseTile = function (detailObject) {
        var {
            styles,
            altText,
            tiles,
            details,
        } = onlyVisibleColumns(detailObject);
        var detailModel = new Backbone.Model({
            data: details,
            altText,
            id: 0,
        });
        var numEntitiesPerRow = detailObject.numEntitiesPerRow || 1;
        var numRows = detailObject.maxHeight;
        var numColumns = detailObject.maxWidth;
        var useUniformUnits = detailObject.useUniformUnits || false;

        var caseTileStyles = views.buildCaseTileStyles(tiles, styles, numRows,
            numColumns, numEntitiesPerRow, useUniformUnits, 'persistent');
        // Style the positioning of the elements within a tile (IE element 1 at grid position 1 / 2 / 4 / 3
        $("#persistent-cell-layout-style").html(caseTileStyles.cellLayoutStyle).data("css-polyfilled", false);
        // Style the grid (IE each tile has 6 rows, 12 columns)
        $("#persistent-cell-grid-style").html(caseTileStyles.cellGridStyle).data("css-polyfilled", false);
        return views.PersistentCaseTileView({
            model: detailModel,
            styles: styles,
            tiles: tiles,
            maxWidth: detailObject.maxWidth,
            maxHeight: detailObject.maxHeight,
            prefix: 'persistent',
            hasInlineTile: detailObject.hasInlineTile,
        });
    };

    return {
        selectDetail: selectDetail,
        selectMenu: selectMenu,
        showMenu: showMenu,
    };
});
