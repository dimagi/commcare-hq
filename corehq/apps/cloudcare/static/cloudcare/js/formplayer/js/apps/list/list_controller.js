/*global FormplayerFrontend */

FormplayerFrontend.module("AppSelect.AppList", function(AppList, FormplayerFrontend, Backbone, Marionette, $){
    AppList.Controller = {
        listApps: function(){
            var fetchingApps = FormplayerFrontend.request("appselect:apps");

            $.when(fetchingApps).done(function (apps) {

                var appListView = new AppList.AppSelectView({
                    collection: apps,
                });

                FormplayerFrontend.regions.main.show(appListView);
            });
        },
    };
});