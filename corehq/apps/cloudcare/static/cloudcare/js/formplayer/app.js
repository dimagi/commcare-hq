/*global Marionette, Backbone */

var FormplayerFrontend = new Marionette.Application();
var tfLoading = hqImport('cloudcare/js/util.js').tfLoading;
var tfLoadingComplete = hqImport('cloudcare/js/util.js').tfLoadingComplete;
var tfSyncComplete = hqImport('cloudcare/js/util.js').tfSyncComplete;
var hideLoading = hqImport('cloudcare/js/util.js').hideLoading;

FormplayerFrontend.on("before:start", function () {
    var RegionContainer = Marionette.LayoutView.extend({
        el: "#app-container",

        regions: {
            main: "#main-region",
        },
    });

    FormplayerFrontend.regions = new RegionContainer();
});

FormplayerFrontend.navigate = function (route, options) {
    options || (options = {});
    Backbone.history.navigate(route, options);
};

FormplayerFrontend.getCurrentRoute = function () {
    return Backbone.history.fragment;
};

FormplayerFrontend.reqres.setHandler('currentUser', function () {
    if (FormplayerFrontend.currentUser) return FormplayerFrontend.currentUser;
    return new FormplayerFrontend.Entities.UserModel();
});

FormplayerFrontend.reqres.setHandler('startForm', function (data) {
    var loadSession = function () {
        debugger;
        data.onLoading = tfLoading;
        data.xform_url="/webforms/player_proxy";
        var sess = new WebFormSession(data);
        sess.loadDirect(data, $('#webforms'), FormplayerFrontend.request('currentUser').language);
    };
    loadSession();
});

FormplayerFrontend.on("start", function (apps, language) {
    FormplayerFrontend.request('currentUser').language = language;
    if (Backbone.history) {
        Backbone.history.start();
        FormplayerFrontend.trigger("apps:storeapps", apps);
        var user = FormplayerFrontend.request('currentUser');
        // will be the same for every domain. TODO: get domain/username/pass from django
        user.domain = apps[0].domain;
        if (this.getCurrentRoute() === "") {
            FormplayerFrontend.trigger("apps:list", apps);
        }
    }
});