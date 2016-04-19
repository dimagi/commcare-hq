FormplayerFrontend.module("AppSelect", function(AppSelect, FormplayerFrontend, Backbone, Marionette, $, _){
    AppSelect.Router(Marionette.Approuter.extend({
        appRoutes: {
            "apps": "listApps",
            "apps/:id/select": "selectApp"
        }
    }));

    var API = {
        listApps: function() {
            AppSelect.List.Controller.listApps();
        },
        selectApp: function() {
            AppSelect.Select.Controller.selectApp(id);
        }
    };

    FormplayerFrontend.on("apps:list", function(){
        AppSelect.navigate("apps");
        API.listApps;
    });

    FormplayerFrontend.on("apps:select", function(id){
        AppSelect.navigate("apps/" + id + "/select");
        API.editContact(id);
    });

});