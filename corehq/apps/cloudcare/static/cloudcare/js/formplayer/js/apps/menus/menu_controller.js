/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $) {
    MenuList.Controller = {
        selectMenu: function (appId, stepList, page, search) {

            var fetchingNextMenu = FormplayerFrontend.request("app:select:menus", appId, stepList, page, search);

            /*
             Determine the next screen to display.  Could be
             a list of commands (modules and/or forms)
             a list of entities (cases) and their details
             */
            $.when(fetchingNextMenu).done(function (menuResponse) {
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
                    tiles: menuResponse.tiles,
                };
                if (menuResponse.type === "commands") {
                    menuListView = new MenuList.MenuListView(menuData);
                    FormplayerFrontend.regions.main.show(menuListView.render());
                }
                else if (menuResponse.type === "entities") {
                    menuListView = new MenuList.CaseListView(menuData);
                    FormplayerFrontend.regions.main.show(menuListView.render());
                }
            });
        },

        showDetail: function (model) {
            var headers = model.options.model.get('detail').headers;
            var details = model.options.model.get('detail').details;
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

            $('#select-case').click(function () {
                FormplayerFrontend.trigger("menu:select", model._index, model.options.model.collection.appId);
            });

            $('#case-detail-modal').find('.modal-body').html(menuListView.render().el);
            $('#case-detail-modal').modal('toggle');
        },
    };
});