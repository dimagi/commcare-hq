FormplayerFrontend.module("AppSelect.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $, _) {
    MenuList.Controller = {
        selectMenu: function (app_id, select_list) {

            var fetchingApps = FormplayerFrontend.request("app:select:menus", app_id, select_list);

            $.when(fetchingApps).done(function (options) {
                if (options.type === "commands") {
                    var menuListView = new MenuList.MenuListView({
                        collection: options,
                        title: options.title
                    });
                }
                else if (options.type === "entities") {
                    var menuListView = new MenuList.CaseListView({
                        collection: options,
                        title: options.title
                    });
                }

                FormplayerFrontend.regions.main.show(menuListView.render());
            });
        },

        showDetail: function (model) {
            headers = model.options.model.attributes.detail.headers;
            details = model.options.model.attributes.detail.details;
            detailModel = [];

            for(var i = 0; i < headers.length; i++){
                obj = {};
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
                collection: detailCollection
            });
            $('#my-modal-body').html(menuListView.render().el);
            $('#myModal').modal('toggle');
        }
    }
});