/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Menus", function (Menus, FormplayerFrontend, Backbone, Marionette, $) {
    Menus.Controller = {
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

                Menus.Controller.showMenu(menuResponse);
            }).fail(function() {
                FormplayerFrontend.trigger('navigateHome');
            });
        },

        selectDetail: function(caseId, detailIndex) {
            var urlObject = Util.currentUrlToObject();
            urlObject.addStep(caseId);
            var fetchingDetails = FormplayerFrontend.request("entity:get:details", urlObject);
            $.when(fetchingDetails).done(function (detailResponse) {
                Menus.Controller.showDetail(detailResponse, detailIndex, caseId);
            }).fail(function() {
                FormplayerFrontend.trigger('navigateHome');
            });
        },

        showMenu: function (menuResponse) {
            var menuListView = Menus.Util.getMenuView(menuResponse);

            if (menuListView) {
                FormplayerFrontend.regions.main.show(menuListView.render());
            }
            if (menuResponse.persistentCaseTile) {
                Menus.Controller.showPersistentCaseTile(menuResponse.persistentCaseTile);
            } else {
                FormplayerFrontend.regions.persistentCaseTile.empty();
            }

            if (menuResponse.breadcrumbs) {
                Menus.Util.showBreadcrumbs(menuResponse.breadcrumbs);
            } else {
                FormplayerFrontend.regions.breadcrumb.empty();
            }
            if (menuResponse.appVersion) {
                FormplayerFrontend.trigger('setVersionInfo', menuResponse.appVersion);
            }
        },

        showPersistentCaseTile: function (persistentCaseTile) {
            var detailView = Menus.Controller.getCaseTile(persistentCaseTile);
            FormplayerFrontend.regions.persistentCaseTile.show(detailView.render());
        },

        showDetail: function (model, detailTabIndex, caseId) {
            var self = this;
            var detailObjects = model.models;
            // If we have no details, just select the entity
            if (detailObjects === null || detailObjects === undefined) {
                FormplayerFrontend.trigger("menu:select", caseId);
                return;
            }
            var detailObject = detailObjects[detailTabIndex];
            var menuListView = Menus.Controller.getDetailList(detailObject);

            var tabModels = _.map(detailObjects, function (detail, index) {
                return {title: detail.title, id: index};
            });
            var tabCollection = new Backbone.Collection();
            tabCollection.reset(tabModels);

            var tabListView = new Menus.Views.DetailTabListView({
                collection: tabCollection,
                showDetail: function (detailTabIndex) {
                    self.showDetail(model, detailTabIndex);
                },
            });

            $('#select-case').off('click').click(function () {
                FormplayerFrontend.trigger("menu:select", caseId);
            });
            $('#case-detail-modal').find('.js-detail-tabs').html(tabListView.render().el);
            $('#case-detail-modal').find('.js-detail-content').html(menuListView.render().el);
            $('#case-detail-modal').modal('show');
        },

        getDetailList: function (detailObject) {
            var headers = detailObject.get('headers');
            var details = detailObject.get('details');
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
            return new Menus.Views.DetailListView({
                collection: detailCollection,
            });
        },

        // return a case tile from a detail object (for persistent case tile)
        getCaseTile: function (detailObject) {
            var detailModel = [];
            var obj = {};
            obj.data = detailObject.details;
            obj.id = 0;
            detailModel.push(obj);
            var detailCollection = new Backbone.Collection();
            detailCollection.reset(detailModel);
            return new Menus.Views.CaseTileListView({
                collection: detailCollection,
                styles: detailObject.styles,
                tiles: detailObject.tiles,
                maxWidth: detailObject.maxWidth,
                maxHeight: detailObject.maxHeight,
            });
        },
    };

    Menus.Util = {
        showBreadcrumbs: function (breadcrumbs) {
            var detailCollection,
                breadcrumbModels;

            breadcrumbModels = _.map(breadcrumbs, function(breadcrumb, idx) {
                return {
                    data: breadcrumb,
                    id: idx,
                };
            });

            detailCollection = new Backbone.Collection(breadcrumbModels);
            var breadcrumbView = new Menus.Views.BreadcrumbListView({
                collection: detailCollection,
            });
            FormplayerFrontend.regions.breadcrumb.show(breadcrumbView.render());
        },

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
                useUniformUnits: menuResponse.useUniformUnits,
            };
            if (menuResponse.type === "commands") {
                return new Menus.Views.MenuListView(menuData);
            } else if (menuResponse.type === "query") {
                return new Menus.Views.QueryListView(menuData);
            }
            else if (menuResponse.type === "entities") {
                if (menuResponse.tiles === null || menuResponse.tiles === undefined) {
                    return new Menus.Views.CaseListView(menuData);
                } else {
                    if (menuResponse.numEntitiesPerRow > 1) {
                        return new Menus.Views.GridCaseTileListView(menuData);
                    } else {
                        return new Menus.Views.CaseTileListView(menuData);
                    }
                }
            }
        },
    };
});
