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

            $.when(fetchingApps).done(function (menus) {

                var menuListView = new MenuList.MenuListView({
                    collection: menus
                });

                FormplayerFrontend.regions.main.show(menuListView);
            });
        }
    }
});