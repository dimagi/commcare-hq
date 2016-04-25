FormplayerFrontend.module("AppSelect.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette, $, _) {
    MenuList.Controller = {
        listMenus: function (app_id) {

            var fetchingApps = FormplayerFrontend.request("app:select:menus", app_id);

            $.when(fetchingApps).done(function (menus) {
                var menuListView = new MenuList.MenuListView({
                    collection: menus
                });

                FormplayerFrontend.regions.main.show(menuListView);
            });
        },

        selectMenu: function (model) {

            var fetchingApps = FormplayerFrontend.request("app:select:menus:select", model);

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