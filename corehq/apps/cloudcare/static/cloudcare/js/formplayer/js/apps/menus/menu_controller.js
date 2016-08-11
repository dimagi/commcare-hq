/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $) {
    MenuList.Controller = {
        selectMenu: function (appId, sessionId, stepList, page, search, queryDict) {

            var fetchingNextMenu = FormplayerFrontend.request("app:select:menus",
                appId,
                sessionId,
                stepList,
                page,
                search,
                queryDict);

            /*
             Determine the next screen to display.  Could be
             a list of commands (modules and/or forms)
             a list of entities (cases) and their details
             */
            $.when(fetchingNextMenu).done(function (menuResponse) {
                MenuList.Controller.showMenu(menuResponse);
            });
        },

        showMenu: function (menuResponse) {
            var menuListView;
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
            };
            if (menuResponse.type === "commands") {
                menuListView = new MenuList.MenuListView(menuData);
                FormplayerFrontend.regions.main.show(menuListView.render());
            } else if (menuResponse.type === "query") {
                menuListView = new MenuList.QueryListView(menuData);
                FormplayerFrontend.regions.main.show(menuListView.render());
            }
            else if (menuResponse.type === "entities") {
                menuListView = new MenuList.CaseListView(menuData);
                FormplayerFrontend.regions.main.show(menuListView.render());
            }

            if (menuResponse.breadcrumbs) {
                MenuList.Controller.showBreadcrumbs(menuResponse.breadcrumbs);
            }
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

        showDetail: function (model, index) {
            var self = this;
            var detailObjects = model.options.model.get('details');
            var detailObject = detailObjects[index];
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
                showDetail: function (index) {
                    self.showDetail(model, index);
                },
            });

            $('#select-case').click(function () {
                FormplayerFrontend.trigger("menu:select", model._index);
            });
            $('#case-detail-modal').find('.detail-tabs').html(tabListView.render().el);
            $('#case-detail-modal').find('.modal-body').html(menuListView.render().el);
            $('#case-detail-modal').modal('show');
        },
    };
});