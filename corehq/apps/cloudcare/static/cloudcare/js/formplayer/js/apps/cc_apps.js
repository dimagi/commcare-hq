FormplayerFrontend.module("AppSelect", function(AppSelect, FormplayerFrontend, Backbone, Marionette, $, _){
    AppSelect.Router = Marionette.AppRouter.extend({
        appRoutes: {
            "apps/:apps": "listApps",
            "apps/:id/select": "selectApp",
            "apps/:apps/store": "storeApps"
        }
    });

    var API = {
        listApps: function() {
            console.log("list apps");
            AppSelect.AppList.Controller.listApps();
        },
        selectApp: function(model) {
            console.log("selectApp API: " + model);
            AppSelect.MenuList.Controller.listMenus(model);
        },
        storeApps: function(apps){
            console.log("CC apps API store apps");
            FormplayerFrontend.request("appselect:storeapps", apps)
        }
    };

    FormplayerFrontend.on("apps:list", function(apps){
        console.log("apps:list: " + apps);
        FormplayerFrontend.navigate("apps");
        API.listApps();
    });

    FormplayerFrontend.on("app:select", function(model){
        console.log("ccapps:appselect" + model);
        FormplayerFrontend.navigate("apps/" + model.attributes._id + "/select");
        API.selectApp(model);
    });

    FormplayerFrontend.on("apps:storeapps", function(apps){
        console.log("apps:storeapps");
        API.storeApps(apps);
        FormplayerFrontend.navigate("apps");
    });

    FormplayerFrontend.on("app:select:")

    AppSelect.on("start", function() {
        new AppSelect.Router({
            controller: API
        });
    });

});