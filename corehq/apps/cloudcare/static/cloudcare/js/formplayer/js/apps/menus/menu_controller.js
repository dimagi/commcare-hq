FormplayerFrontend.module("AppSelect.MenuList", function(MenuList, FormplayerFrontend, Backbone, Marionette, $, _){
    MenuList.Controller = {
        listMenus: function(app){

            console.log("Listing apps: " + app);

            var fetchingApps = FormplayerFrontend.request("app:select:menus", app);

            $.when(fetchingApps).done(function (menus) {

                //debugger;

                var menuListView = new MenuList.MenuListView({
                    collection: menus
                });

                FormplayerFrontend.regions.main.show(menuListView);
            });
        }
    }
});