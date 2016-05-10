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
            AppSelect.List.Controller.listApps();
        },
        selectApp: function() {
            console.log("select app");
            //AppSelect.Select.Controller.selectApp(id);
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

    FormplayerFrontend.on("apps:select", function(id){
        FormplayerFrontend.navigate("apps/" + id + "/select");
        API.selectApp(id);
    });

    FormplayerFrontend.on("apps:storeapps", function(apps){
        console.log("apps:storeapps");
        API.storeApps(apps);
        FormplayerFrontend.navigate("apps");
    })

});