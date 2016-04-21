FormplayerFrontend.module("AppSelect.MenuList", function(MenuList, FormplayerFrontend, Backbone, Marionette, $, _){
    MenuList.Controller = {
        listMenus: function(app){

            var fetchingApps = FormplayerFrontend.request("app:select:menus", app);

            $.when(fetchingApps).done(function (menus) {

                var menuListView = new MenuList.MenuListView({
                    collection: menus
                });

                FormplayerFrontend.regions.main.show(menuListView);
            });
        }
    }
});