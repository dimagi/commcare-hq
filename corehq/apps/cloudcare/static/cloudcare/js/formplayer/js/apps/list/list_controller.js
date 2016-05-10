FormplayerFrontend.module("AppSelect.List", function(List, FormplayerFrontend, Backbone, Marionette, $, _){
    List.Controller = {
        listApps: function(){
            var fetchingApps = FormplayerFrontend.request("appselect:apps")

            $.when(fetchingApps).done(function (apps) {

                var contactsListView = new List.AppSelectView({
                    collection: apps
                });

                FormplayerFrontend.regions.main.show(contactsListView);
            });
        }
    }
});