/*global FormplayerFrontend */

FormplayerFrontend.module("AppSelect.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $, _) {
    MenuList.Controller = {
        selectMenu: function (appId, stepList) {

            var fetchingNextMenu = FormplayerFrontend.request("app:select:menus", appId, stepList);

            /*
             Determine the next screen to display.  Could be
             a list of commands (modules and/or forms)
             a list of entities (cases) and their details
             a form to trigger form entry with
             */
            $.when(fetchingNextMenu).done(function (menuResponse) {
                var menuListView;
                var menuData = {collection: menuResponse,
                    title: menuResponse.title,
                    headers: menuResponse.headers,
                    widthHints: menuResponse.widthHints,
                    action: menuResponse.action};
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
            var headers = model.options.model.attributes.detail.headers;
            var details = model.options.model.attributes.detail.details;
            var detailModel = [];
            // we need to map the details and headers JSON to a list for a Backbone Collection
            for (var i = 0; i < headers.length; i++) {
                var obj = {};
                obj.data = details[i];
                obj.header = headers[i];
                obj.id = i;
                detailModel.push(obj);
            }
            var lst = _.map(detailModel, function (val) {
                return {id: val.id, data: val.data, header: val.header};
            });

            var detailCollection = new Backbone.Collection();
            detailCollection.reset(lst);
            var menuListView = new MenuList.DetailListView({
                collection: detailCollection,
            });

            var selectCase = function(){
                FormplayerFrontend.trigger("menu:select", model._index, model.options.model.collection.appId);
            };

            $('#case-detail-modal').find('.modal-body').html(menuListView.render().el);
            $('#select-case').click(function (){
                selectCase();
            });
            $('#case-detail-modal').modal('toggle');
        },
    };
});