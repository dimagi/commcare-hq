var FormplayerFrontend = new Marionette.Application();

FormplayerFrontend.on("before:start", function () {
    var RegionContainer = Marionette.LayoutView.extend({
        el: "#app-container",

        regions: {
            main: "#main-region"
        }
    });

    FormplayerFrontend.regions = new RegionContainer();
});

FormplayerFrontend.navigate = function (route, options) {
    options || (options = {});
    Backbone.history.navigate(route, options);
};

FormplayerFrontend.getCurrentRoute = function () {
    return Backbone.history.fragment
};

FormplayerFrontend.on("start", function (apps) {
    console.log("Storing: " + apps);

    //apps = new Entities.AppSelectCollection(apps);

    FormplayerFrontend.trigger("apps:storeapps", apps);

    //console.log("Apps: " + apps);
    if (this.getCurrentRoute() === undefined) {
        console.log("triggering apps:list");
        FormplayerFrontend.trigger("apps:list", apps);
    }
})