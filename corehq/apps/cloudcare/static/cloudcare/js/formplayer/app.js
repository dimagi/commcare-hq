/*global Marionette, Backbone */

var FormplayerFrontend = new Marionette.Application();

var hideLoading = hqImport('cloudcare/js/util.js').hideLoading;
var showError = hqImport('cloudcare/js/util.js').showError;
var showSuccess = hqImport('cloudcare/js/util.js').showSuccess;
var showLoading = hqImport('cloudcare/js/util.js').showLoading;
var tfLoading = hqImport('cloudcare/js/util.js').tfLoading;
var tfLoadingComplete = hqImport('cloudcare/js/util.js').tfLoadingComplete;
var tfSyncComplete = hqImport('cloudcare/js/util.js').tfSyncComplete;

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

FormplayerFrontend.reqres.setHandler('resourceMap', function (resource_path, app_id) {
    var currentApp = FormplayerFrontend.request('currentApp', app_id);
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

FormplayerFrontend.reqres.setHandler('currentApp', function (app_id) {
    var fetchingApp = FormplayerFrontend.request("appselect:getApp", app_id);
    return fetchingApp;
});

FormplayerFrontend.reqres.setHandler('startForm', function (data) {
    var loadSession = function () {

        $('#app-container').html("");

        data.onLoading = tfLoading;
        data.onLoadingComplete = tfLoadingComplete;
        data.xform_url = "/webforms/player_proxy";
        data.domain = "test"
        data.onerror = function (resp) {
            showError(resp.human_readable_message || resp.message, $("#cloudcare-notifications"));
            //cloudCare.dispatch.trigger("form:error", form, caseModel);
        };
        data.onload = function (adapter, resp) {
            //cloudCare.dispatch.trigger("form:ready", form, caseModel);
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
                            + translatedStrings.unknownErrorDetail + " (" + submitUrl + ")");
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