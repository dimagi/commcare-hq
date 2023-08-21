/*global Backbone */

hqDefine("cloudcare/js/formplayer/menus/controller", function () {
    var constants = hqImport("cloudcare/js/formplayer/constants"),
        markdown = hqImport("cloudcare/js/markdown"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        formplayerUtils = hqImport("cloudcare/js/formplayer/utils/utils"),
        menusUtils = hqImport("cloudcare/js/formplayer/menus/utils"),
        views = hqImport("cloudcare/js/formplayer/menus/views"),
        toggles = hqImport("hqwebapp/js/toggles"),
        QueryListView = hqImport("cloudcare/js/formplayer/menus/views/query"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data").get,
        Collection = hqImport("cloudcare/js/formplayer/menus/collections");
    var selectMenu = function (options) {

        options.preview = FormplayerFrontend.currentUser.displayOptions.singleAppMode;

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
                        "required. If this persists, please report an issue to CommCareHQ");
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
        var fetchingDetails = FormplayerFrontend.getChannel().request("entity:get:details", urlObject, isPersistent);
        $.when(fetchingDetails).done(function (detailResponse) {
            showDetail(detailResponse, detailIndex, caseId, isMultiSelect);
        }).fail(function () {
            FormplayerFrontend.trigger('navigateHome');
        });
    };

    var showMenu = function (menuResponse) {
        var menuListView = menusUtils.getMenuView(menuResponse);
        var appPreview = FormplayerFrontend.currentUser.displayOptions.singleAppMode;
        var enablePrintOption = !menuResponse.queryKey;
        var sidebarEnabled = toggles.toggleEnabled('SPLIT_SCREEN_CASE_SEARCH') && !appPreview;

        if (sidebarEnabled && menuResponse.type === "query") {
            var menuData = menusUtils.getMenuData(menuResponse);
            menuData["triggerEmptyCaseList"] = true;
            menuData["sidebarEnabled"] = true;
            menuData["description"] = menuResponse.description;

            var caseListView = menusUtils.getCaseListView(menuResponse);
            FormplayerFrontend.regions.getRegion('main').show(caseListView(menuData));
        } else if (menuListView) {
            FormplayerFrontend.regions.getRegion('main').show(menuListView);
        }
        if (menuResponse.persistentCaseTile && !appPreview) {
            showPersistentCaseTile(menuResponse.persistentCaseTile);
        } else {
            FormplayerFrontend.regions.getRegion('persistentCaseTile').empty();
        }

        var queryResponse = menuResponse.queryResponse;
        if (sidebarEnabled && menuResponse.type === "entities" && queryResponse)  {
            var queryCollection = new Collection(queryResponse.displays);
            FormplayerFrontend.regions.getRegion('sidebar').show(
                QueryListView({
                    collection: queryCollection,
                    title: menuResponse.title,
                    description: menuResponse.description,
                    sidebarEnabled: true,
                }).render()
            );
        } else if (sidebarEnabled && menuResponse.type === "query") {
            FormplayerFrontend.regions.getRegion('sidebar').show(
                QueryListView({
                    collection: menuResponse,
                    title: menuResponse.title,
                    description: menuResponse.description,
                    sidebarEnabled: true,
                }).render()
            );
        } else {
            FormplayerFrontend.regions.getRegion('sidebar').empty();
        }

        if (menuResponse.breadcrumbs) {
            menusUtils.showBreadcrumbs(menuResponse.breadcrumbs);
            if (!appPreview && ((menuResponse.langs && menuResponse.langs.length > 1) || enablePrintOption)) {
                menusUtils.showFormMenu(menuResponse.langs, initialPageData('lang_code_name_mapping'));
            }
        } else {
            FormplayerFrontend.regions.getRegion('breadcrumb').empty();
        }
        if (menuResponse.appVersion) {
            FormplayerFrontend.trigger('setVersionInfo', menuResponse.appVersion);
        }
    };

    var showPersistentCaseTile = function (persistentCaseTile) {
        var detailView = getCaseTile(persistentCaseTile);
        FormplayerFrontend.regions.getRegion('persistentCaseTile').show(detailView.render());
    };

    var showDetail = function (model, detailTabIndex, caseId, isMultiSelect) {
        var detailObjects = model.models;
        // If we have no details, just select the entity
        if (detailObjects === null || detailObjects === undefined || detailObjects.length === 0) {
            if (isMultiSelect) {
                FormplayerFrontend.trigger("multiSelect:updateCases", constants.MULTI_SELECT_ADD, [caseId]);
            } else {
                FormplayerFrontend.trigger("menu:select", caseId);
            }
            return;
        }
        var detailObject = detailObjects[detailTabIndex];
        var menuListView = getDetailList(detailObject);

        var tabModels = _.map(detailObjects, function (detail, index) {
            return {title: detail.get('title'), id: index, active: index === detailTabIndex};
        });
        var tabCollection = new Backbone.Collection();
        tabCollection.reset(tabModels);

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
        $('#case-detail-modal').find('.js-detail-content').html(menuListView.render().el);
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
                title: detailObject.get('title'),
            };
            return views.CaseListDetailView(menuData);
        }

        // This is a regular detail, displaying name-value pairs
        var headers = detailObject.get('headers');
        var details = detailObject.get('details');
        var styles = detailObject.get('styles');
        var detailModel = [];
        // we need to map the details and headers JSON to a list for a Backbone Collection
        for (i = 0; i < headers.length; i++) {
            var obj = {};
            obj.data = details[i];
            obj.header = headers[i];
            obj.style = styles[i];
            obj.id = i;
            if (obj.style.displayFormat === 'Markdown') {
                obj.html = markdown.render(details[i]);
            }
            detailModel.push(obj);
        }
        var detailCollection = new Backbone.Collection();
        detailCollection.reset(detailModel);
        return views.DetailListView({
            collection: detailCollection,
        });
    };

    // return a case tile from a detail object (for persistent case tile)
    var getCaseTile = function (detailObject) {
        var detailModel = new Backbone.Model({
            data: detailObject.details,
            id: 0,
        });
        var numEntitiesPerRow = detailObject.numEntitiesPerRow || 1;
        var numRows = detailObject.maxHeight;
        var numColumns = detailObject.maxWidth;
        var useUniformUnits = detailObject.useUniformUnits || false;
        var caseTileStyles = views.buildCaseTileStyles(detailObject.tiles, detailObject.styles, numRows,
            numColumns, numEntitiesPerRow, useUniformUnits, 'persistent');
        // Style the positioning of the elements within a tile (IE element 1 at grid position 1 / 2 / 4 / 3
        $("#persistent-cell-layout-style").html(caseTileStyles.cellLayoutStyle).data("css-polyfilled", false);
        // Style the grid (IE each tile has 6 rows, 12 columns)
        $("#persistent-cell-grid-style").html(caseTileStyles.cellGridStyle).data("css-polyfilled", false);
        return views.PersistentCaseTileView({
            model: detailModel,
            styles: detailObject.styles,
            tiles: detailObject.tiles,
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
