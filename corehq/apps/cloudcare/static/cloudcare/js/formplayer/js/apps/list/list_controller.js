/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.AppList", function(AppList, FormplayerFrontend, Backbone, Marionette, $){
    AppList.Controller = {
        listApps: function(){
            var fetchingApps = FormplayerFrontend.request("appselect:apps");

            $.when(fetchingApps).done(function (apps) {

                var appListView = new AppList.SessionNavigateView({
                    collection: apps,
                });

                var appGridView = new AppList.GridView({
                    collection: apps,
                });

                FormplayerFrontend.regions.main.show(appGridView);
            });
        },
    };
});