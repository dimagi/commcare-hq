/*global Marionette, Backbone */

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
    var loadSession = function () {

        FormplayerFrontend.request("clearMenu");

        data.onLoading = tfLoading;
        data.onLoadingComplete = tfLoadingComplete;
        data.xform_url = "/webforms/player_proxy";
        data.domain = "test"
        data.onerror = function (resp) {
            showError(resp.human_readable_message || resp.message, $("#cloudcare-notifications"));
        };
        data.onsubmit = function (resp) {
            // window.mainView.router.view.dirty = false;
            // post to receiver
            var xml = resp.output;
            var postUrl = resp.postUrl;
            $.ajax({
                type: 'POST',
                url: postUrl,
                data: xml,
                success: function () {
                    $('#webforms').html("");
                    // TODO form linking
                    FormplayerFrontend.trigger("apps:list");
                    showSuccess(translatedStrings.saved, $("#cloudcare-notifications"), 2500);
                },
                error: function (resp, status, message) {
                    if (message) {
                        message = translatedStrings.errSavingDetail + message;
                    } else {
                        message = translatedStrings.unknownError + status + " " + resp.status;
                        if (resp.status === 0) {
                            message = (message + ". "
                            + translatedStrings.unknownErrorDetail + " (" + postUrl + ")");
                        }
                    }
                    data.onerror({message: message});
                    // TODO change submit button text to something other than
                    // "Submitting..." and prevent "All changes saved!" message
                    // banner at top of the form.
                }
            });
        };
        var sess = new WebFormSession(data);
        sess.loadDirect(data, $('#webforms'), FormplayerFrontend.request('currentUser').language);
    };
    loadSession();
});

FormplayerFrontend.on("start", function (apps, language) {
    FormplayerFrontend.request('currentUser').language = language;
    FormplayerFrontend.request('currentUser').apps = apps;
    if (Backbone.history) {
        Backbone.history.start();
        var user = FormplayerFrontend.request('currentUser');
        // will be the same for every domain. TODO: get domain/username/pass from django
        user.domain = apps[0].domain;
        if (this.getCurrentRoute() === "") {
            FormplayerFrontend.trigger("apps:list", apps);
        }
    }
});