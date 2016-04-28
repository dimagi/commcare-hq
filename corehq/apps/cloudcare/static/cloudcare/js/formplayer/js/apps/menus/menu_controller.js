FormplayerFrontend.module("AppSelect.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $, _) {
    MenuList.Controller = {
        selectMenu: function (app_id, select_list) {

            var fetchingApps = FormplayerFrontend.request("app:select:menus", app_id, select_list);

            $.when(fetchingApps).done(function (options) {
                if(options.type === "commands") {
                    var menuListView = new MenuList.MenuListView({
                        collection: options,
                        title: options.title
                    });
                }
                else if(options.type === "entities") {
                    var menuListView = new MenuList.CaseListView({
                        collection: options,
                        title: options.title
                    });
                }
                else if(options.type === "details") {
                    var menuListView = new MenuList.DetailListView({
                        collection: options,
                        title: options.title
                    });
                }

                FormplayerFrontend.regions.main.show(menuListView.render());
            });
        }
    }
});