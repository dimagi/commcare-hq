/*global FormplayerFrontend, Util */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $) {
    MenuList.Controller = {
        selectMenu: function (options) {

            var fetchingNextMenu = FormplayerFrontend.request("app:select:menus", options);

            /*
             Determine the next screen to display.  Could be
             a list of commands (modules and/or forms)
             a list of entities (cases) and their details
             */
            $.when(fetchingNextMenu).done(function (menuResponse) {

                // show any notifications from Formplayer
                if (menuResponse.notification && !_.isNull(menuResponse.notification.message)) {
                    FormplayerFrontend.request("handleNotification", menuResponse.notification);
                }

                // If redirect was set, clear and go home.
                if (menuResponse.clearSession) {
                    FormplayerFrontend.trigger("apps:currentApp");
                    return;
                }

                var urlObject = Util.currentUrlToObject();
                // If we don't have an appId in the URL (usually due to form preview)
                // then parse the appId from the response.
                if (urlObject.appId === undefined || urlObject.appId === null) {
                    if (menuResponse.appId === null || menuResponse.appId === undefined) {
                        FormplayerFrontend.request('showError', "Response did not contain appId even though it was" +
                            "required. If this persists, please report an issue to CommCareHQ");
                        FormplayerFrontend.trigger("apps:list", options.apps);
                        return;
                    }
                    urlObject.appId = menuResponse.appId;
                    Util.setUrlToObject(urlObject);
                }

                MenuList.Controller.showMenu(menuResponse);
            });
        },

        showMenu: function (menuResponse) {
            var menuListView = MenuList.Util.getMenuView(menuResponse);

            if (menuListView) {
                FormplayerFrontend.regions.main.show(menuListView.render());
            }

            if (menuResponse.breadcrumbs) {
                MenuList.Controller.showBreadcrumbs(menuResponse.breadcrumbs);
            }
            if (menuResponse.appVersion) {
                MenuList.Controller.showAppVersion(menuResponse.appVersion);
            }
        },

        showAppVersion: function (appVersion) {
            $("#version-info").text(appVersion);
        },

        showBreadcrumbs: function (breadcrumbs) {
            var breadcrumbsModel = [];
            for (var i = 0; i < breadcrumbs.length; i++) {
                var obj = {};
                obj.data = breadcrumbs[i];
                obj.id = i;
                breadcrumbsModel.push(obj);
            }
            var detailCollection = new Backbone.Collection();
            detailCollection.reset(breadcrumbsModel);
            var breadcrumbView = new MenuList.BreadcrumbListView({
                collection: detailCollection,
            });
            FormplayerFrontend.regions.breadcrumb.show(breadcrumbView.render());
        },

        showDetail: function (model, detailTabIndex) {
            var self = this;
            var detailObjects = model.options.model.get('details');
            // If we have no details, just select the entity
            if (detailObjects === null || detailObjects === undefined) {
                FormplayerFrontend.trigger("menu:select", model.model.get('id'));
                return;
            }
            var detailObject = detailObjects[detailTabIndex];
            var headers = detailObject.headers;
            var details = detailObject.details;
            var detailModel = [];
            // we need to map the details and headers JSON to a list for a Backbone Collection
            for (var i = 0; i < headers.length; i++) {
                var obj = {};
                obj.data = details[i];
                obj.header = headers[i];
                obj.id = i;
                detailModel.push(obj);
            }
            var detailCollection = new Backbone.Collection();
            detailCollection.reset(detailModel);
            var menuListView = new MenuList.DetailListView({
                collection: detailCollection,
            });

            var tabModels = _.map(detailObjects, function (detail, index) {
                return {title: detail.title, id: index};
            });
            var tabCollection = new Backbone.Collection();
            tabCollection.reset(tabModels);
            var tabListView = new MenuList.DetailTabListView({
                collection: tabCollection,
                showDetail: function (detailTabIndex) {
                    self.showDetail(model, detailTabIndex);
                },
            });

            $('#select-case').unbind('click').click(function () {
                FormplayerFrontend.trigger("menu:select", model.model.get('id'));
            });
            $('#case-detail-modal').find('.detail-tabs').html(tabListView.render().el);
            $('#case-detail-modal').find('.modal-body').html(menuListView.render().el);
            $('#case-detail-modal').modal('show');
        },
    };

    MenuList.Util = {
        getMenuView: function (menuResponse) {
            var menuData = {
                collection: menuResponse,
                title: menuResponse.title,
                headers: menuResponse.headers,
                widthHints: menuResponse.widthHints,
                action: menuResponse.action,
                pageCount: menuResponse.pageCount,
                currentPage: menuResponse.currentPage,
                styles: menuResponse.styles,
                type: menuResponse.type,
                sessionId: menuResponse.sessionId,
                tiles: menuResponse.tiles,
                numEntitiesPerRow: menuResponse.numEntitiesPerRow,
                maxHeight: menuResponse.maxHeight,
                maxWidth: menuResponse.maxWidth,
            };
            if (menuResponse.type === "commands") {
                return new MenuList.MenuListView(menuData);
            } else if (menuResponse.type === "query") {
                return new MenuList.QueryListView(menuData);
            }
            else if (menuResponse.type === "entities") {
                if (menuResponse.tiles === null || menuResponse.tiles === undefined) {
                    return new MenuList.CaseListView(menuData);
                } else {
                    if (menuResponse.numEntitiesPerRow > 1) {
                        return new MenuList.GridCaseTileListView(menuData);
                    } else {
                        return new MenuList.CaseTileListView(menuData);
                    }
                }
            }
        },
    };
});
