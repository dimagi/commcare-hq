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
    console.log("Navigating in app with route: " + route);
    options || (options = {});
    console.log("options: " + options);
    Backbone.history.navigate(route, options);
};

FormplayerFrontend.getCurrentRoute = function () {
    return Backbone.history.fragment;
};

FormplayerFrontend.reqres.setHandler('currentUser', function () {
    if (FormplayerFrontend.currentUser) return FormplayerFrontend.currentUser;

    var user = FormplayerFrontend.currentUser = new FormplayerFrontend.Entities.UserModel();
    return user;
});


FormplayerFrontend.on("start", function (apps) {
    if (Backbone.history) {
        Backbone.history.start();
        FormplayerFrontend.trigger("apps:storeapps", apps);
        var user = FormplayerFrontend.request('currentUser');
        user.domain = apps[0].domain;
        if (this.getCurrentRoute() === "") {
            FormplayerFrontend.trigger("apps:list", apps);
        }
    }
});