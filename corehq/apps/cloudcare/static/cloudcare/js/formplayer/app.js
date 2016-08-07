/*global Marionette, Backbone, WebFormSession, Util, Entities */

/**
 * The primary Marionette application managing menu navigation and launching form entry
 */

var FormplayerFrontend = new Marionette.Application();

var showError = hqImport('cloudcare/js/util.js').showError;
var showSuccess = hqImport('cloudcare/js/util.js').showSuccess;
var tfLoading = hqImport('cloudcare/js/util.js').tfLoading;
var tfLoadingComplete = hqImport('cloudcare/js/util.js').tfLoadingComplete;
var tfSyncComplete = hqImport('cloudcare/js/util.js').tfSyncComplete;

FormplayerFrontend.on("before:start", function () {
    var RegionContainer = Marionette.LayoutView.extend({
        el: "#menu-container",

        regions: {
            main: "#menu-region",
            breadcrumb: "#breadcrumb-region",
            caseTileStyle: "#case-tile-style",
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

$(document).bind("ajaxStart", function () {
    $(".formplayer-request").addClass('formplayer-requester-disabled');
    tfLoading();
}).bind("ajaxStop", function () {
    $(".formplayer-request").removeClass('formplayer-requester-disabled');
    tfLoadingComplete();
});

FormplayerFrontend.reqres.setHandler('error', function (errorMessage) {
    showError(errorMessage, $("#cloudcare-notifications"), 10000);
});

FormplayerFrontend.reqres.setHandler('startForm', function (data) {
    FormplayerFrontend.request("clearMenu");

    data.onLoading = tfLoading;
    data.onLoadingComplete = tfLoadingComplete;
    var user = FormplayerFrontend.request('currentUser');
    data.xform_url = user.formplayer_url;
    data.domain = user.domain;
    data.formplayerEnabled = true;
    data.onerror = function (resp) {
        showError(resp.human_readable_message || resp.message, $("#cloudcare-notifications"));
    };
    data.onsubmit = function (resp) {
        if (resp.status === "success") {
            FormplayerFrontend.request("clearForm");
            showSuccess(gettext("Form successfully saved"), $("#cloudcare-notifications"), 10000);

            if(resp.nextScreen !== null && resp.nextScreen !== undefined) {
                FormplayerFrontend.trigger("renderResponse", resp.nextScreen);
            } else {
                FormplayerFrontend.trigger("apps:currentApp");
            }
        } else {
            showError(resp.output, $("#cloudcare-notifications"));
        }
        // TODO form linking
    };
    data.formplayerEnabled = true;
    data.resourceMap = function(resource_path) {
        var oldRoute = Backbone.history.getFragment();
        var appId = Util.getAppId(oldRoute);
        return FormplayerFrontend.request('resourceMap', resource_path, appId);
    };
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

FormplayerFrontend.on("sync", function () {
    var user = FormplayerFrontend.request('currentUser');
    var username = user.username;
    var domain = user.domain;
    var formplayer_url = user.formplayer_url;
    var options = {
        url: formplayer_url + "/sync-db",
        data: JSON.stringify({"username": username, "domain": domain}),
    };
    Util.setCrossDomainAjaxOptions(options);
    var resp = $.ajax(options);
    resp.done(function () {
        tfSyncComplete(false);
    });
    resp.error(function () {
        tfSyncComplete(true);
    });
});