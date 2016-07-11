/*global Marionette, Backbone, WebFormSession */

/**
 * The primary Marionette application managing menu navigation and launching form entry
 */

var FormplayerFrontend = new Marionette.Application();

var showError = hqImport('cloudcare/js/util.js').showError;
var showSuccess = hqImport('cloudcare/js/util.js').showSuccess;
var tfLoading = hqImport('cloudcare/js/util.js').tfLoading;
var tfLoadingComplete = hqImport('cloudcare/js/util.js').tfLoadingComplete;

FormplayerFrontend.on("before:start", function () {
    var RegionContainer = Marionette.LayoutView.extend({
        el: "#menu-container",

        regions: {
            main: "#menu-region",
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

/**
 * This function maps a jr:// media path to its HTML path IE
 * jr://images/icon/mother.png -> https://commcarehq.org/hq/multimedia/file/CommCareImage/[app_id]/mother.png
 * The actual mapping is contained in the app Couch document
 */
FormplayerFrontend.reqres.setHandler('resourceMap', function (resource_path, app_id) {
    var currentApp = FormplayerFrontend.request("appselect:getApp", app_id);
    if (resource_path.substring(0, 7) === 'http://') {
        return resource_path;
    } else if (currentApp.attributes.hasOwnProperty("multimedia_map") &&
        currentApp.attributes.multimedia_map.hasOwnProperty(resource_path)) {
        var resource = currentApp.attributes.multimedia_map[resource_path];
        var id = resource.multimedia_id;
        var media_type = resource.media_type;
        var name = _.last(resource_path.split('/'));
        return '/hq/multimedia/file/' + media_type + '/' + id + '/' + name;
    }
});

FormplayerFrontend.reqres.setHandler('currentUser', function () {
    if (!FormplayerFrontend.currentUser) {
        FormplayerFrontend.currentUser = new FormplayerFrontend.Entities.UserModel();
    }
    return FormplayerFrontend.currentUser;
});

FormplayerFrontend.reqres.setHandler('clearForm', function () {
    $('#webforms').html("");
});

FormplayerFrontend.reqres.setHandler('clearMenu', function () {
    $('#menu-region').html("");
});

FormplayerFrontend.reqres.setHandler('startForm', function (data) {
    FormplayerFrontend.request("clearMenu");

    data.onLoading = tfLoading;
    data.onLoadingComplete = tfLoadingComplete;
    data.xform_url = FormplayerFrontend.request('currentUser').formplayer_url;
    data.formplayerEnabled = true;
    //TODO yeah
    data.domain = "test";
    data.onerror = function (resp) {
        showError(resp.human_readable_message || resp.message, $("#cloudcare-notifications"));
    };
    data.onsubmit = function (resp) {
        if(resp.status === "success") {
            FormplayerFrontend.request("clearForm");
            FormplayerFrontend.trigger("apps:list");
            showSuccess(gettext("Form successfully saved"), $("#cloudcare-notifications"), 2500);
        } else {
            showError(resp.output, $("#cloudcare-notifications"));
        }
        // TODO form linking
    };
    data.formplayerEnabled = true;
    var sess = new WebFormSession(data);
    sess.renderFormXml(data, $('#webforms'));
});

FormplayerFrontend.on("start", function (options) {
    var user = FormplayerFrontend.request('currentUser');
    user.username = options.username;
    user.language = options.language;
    user.apps = options.apps;
    user.domain = options.domain;
    user.formplayer_url = options.formplayer_url;
    if (Backbone.history) {
        Backbone.history.start();
        // will be the same for every domain. TODO: get domain/username/pass from django
        if (this.getCurrentRoute() === "") {
            FormplayerFrontend.trigger("apps:list", options.apps);
        }
    }
});