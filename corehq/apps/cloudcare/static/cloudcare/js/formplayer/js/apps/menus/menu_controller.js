/*global FormplayerFrontend */

FormplayerFrontend.module("AppSelect.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $, _) {
    MenuList.Controller = {
        selectMenu: function (app_id, select_list) {

            var fetchingApps = FormplayerFrontend.request("app:select:menus", app_id, select_list);

            $.when(fetchingApps).done(function (options) {
                var menuListView;
                if (options.type === "commands") {
                    menuListView = new MenuList.MenuListView({
                        collection: options,
                        title: options.title,
                    });
                    FormplayerFrontend.regions.main.show(menuListView.render());
                }
                else if (options.type === "entities") {
                    menuListView = new MenuList.CaseListView({
                        collection: options,
                        title: options.title,
                    });
                    FormplayerFrontend.regions.main.show(menuListView.render());
                } else{
                    //TODO: error handle this, we didn't recognize the JSON resposne
                }
            });
        },

        showDetail: function (model) {
            var headers = model.options.model.attributes.detail.headers;
            var details = model.options.model.attributes.detail.details;
            var detailModel = [];
            // we need to map the details and headers JSON to a list for a Backbone Collection
            for(var i = 0; i < headers.length; i++){
                var obj = {};
                obj.data = details[i];
                obj.header = headers[i];
                obj.id = i;
                detailModel.push(obj);
            }
            var lst = _.map(detailModel, function(val) {
                return {id: val.id, data: val.data, header: val.header};
            });

            var detailCollection = new Backbone.Collection();
            detailCollection.reset(lst);
            var menuListView = new MenuList.DetailListView({
                collection: detailCollection,
            });
            $('#my-modal-body').html(menuListView.render().el);
            $('#myModal').modal('toggle');
        },
    };
});