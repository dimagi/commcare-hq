/*global Marionette, Backbone, WebFormSession, Util */

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
            persistentCaseTile: "#persistent-case-tile",
            phoneModeNavigation: '#phone-mode-navigation',
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
    if (!currentApp) {
        console.warn('App is undefined for app_id: ' + app_id);
        console.warn('Not processing resource: ' + resource_path);
        return;
    }
    if (resource_path.substring(0, 7) === 'http://') {
        return resource_path;
    } else if (!_.isEmpty(currentApp.get("multimedia_map"))) {
        var resource = currentApp.get('multimedia_map')[resource_path];
        if (!resource) {
            console.warn('Unable to find resource ' + resource_path + 'in multimedia map');
            return;
        }
        var id = resource.multimedia_id;
        var media_type = resource.media_type;
        var name = _.last(resource_path.split('/'));
        return '/hq/multimedia/file/' + media_type + '/' + id + '/' + name;
    }
});

FormplayerFrontend.reqres.setHandler('gridPolyfillPath', function(path) {
    if (path) {
        FormplayerFrontend.gridPolyfillPath = path;
    } else {
        return FormplayerFrontend.gridPolyfillPath;
    }
});

FormplayerFrontend.reqres.setHandler('currentUser', function () {
    if (!FormplayerFrontend.currentUser) {
        FormplayerFrontend.currentUser = new FormplayerFrontend.Entities.UserModel();
    }
    return FormplayerFrontend.currentUser;
});

FormplayerFrontend.on('clearForm', function () {
    $('#webforms').html("");
});

FormplayerFrontend.reqres.setHandler('clearMenu', function () {
    $('#menu-region').html("");
});

$(document).on("ajaxStart", function () {
    $(".formplayer-request").addClass('formplayer-requester-disabled');
    tfLoading();
}).on("ajaxStop", function () {
    $(".formplayer-request").removeClass('formplayer-requester-disabled');
    tfLoadingComplete();
});

FormplayerFrontend.reqres.setHandler('showError', function (errorMessage) {
    showError(errorMessage, $("#cloudcare-notifications"), 10000);
});

FormplayerFrontend.reqres.setHandler('showSuccess', function(successMessage) {
    showSuccess(successMessage, $("#cloudcare-notifications"), 10000);
});

FormplayerFrontend.reqres.setHandler('handleNotification', function(notification) {
    if(notification.error){
        FormplayerFrontend.request('showError', notification.message);
    } else{
        FormplayerFrontend.request('showSuccess', notification.message);
    }
});

FormplayerFrontend.on('startForm', function (data) {
    FormplayerFrontend.request("clearMenu");

    data.onLoading = tfLoading;
    data.onLoadingComplete = tfLoadingComplete;
    var user = FormplayerFrontend.request('currentUser');
    data.xform_url = user.formplayer_url;
    data.domain = user.domain;
    data.username = user.username;
    data.formplayerEnabled = true;
    data.onerror = function (resp) {
        showError(resp.human_readable_message || resp.message, $("#cloudcare-notifications"));
    };
    data.onsubmit = function (resp) {
        if (resp.status === "success") {
            FormplayerFrontend.trigger("clearForm");
            showSuccess(gettext("Form successfully saved"), $("#cloudcare-notifications"), 10000);

            // After end of form nav, we want to clear everything except app and sesson id
            var urlObject = Util.currentUrlToObject();
            urlObject.onSubmit();
            Util.setUrlToObject(urlObject);

            if(resp.nextScreen !== null && resp.nextScreen !== undefined) {
                FormplayerFrontend.trigger("renderResponse", resp.nextScreen);
            } else if(urlObject.appId !== null && urlObject.appId !== undefined) {
                FormplayerFrontend.trigger("apps:currentApp");
            } else {
                FormplayerFrontend.navigate('/apps', { trigger: true });
            }
        } else {
            showError(resp.output, $("#cloudcare-notifications"));
        }
    };
    data.formplayerEnabled = true;
    data.debuggerEnabled = user.debuggerEnabled;
    data.resourceMap = function(resource_path) {
        var urlObject = Util.currentUrlToObject();
        var appId = urlObject.appId;
        return FormplayerFrontend.request('resourceMap', resource_path, appId);
    };
    var sess = new WebFormSession(data);
    sess.renderFormXml(data, $('#webforms'));
});

FormplayerFrontend.on("start", function (options) {
    var user = FormplayerFrontend.request('currentUser'),
        appId;
    user.username = options.username;
    user.language = options.language;
    user.apps = options.apps;
    user.domain = options.domain;
    user.formplayer_url = options.formplayer_url;
    user.debuggerEnabled = options.debuggerEnabled;
    FormplayerFrontend.request('gridPolyfillPath', options.gridPolyfillPath);
    if (Backbone.history) {
        Backbone.history.start();
        // will be the same for every domain. TODO: get domain/username/pass from django
        if (this.getCurrentRoute() === "") {
            if (options.phoneMode) {
                appId = options.apps[0]['_id'];

                FormplayerFrontend.trigger('setAppDisplayProperties', options.apps[0]);
                FormplayerFrontend.trigger("app:singleApp", appId);
            } else {
                FormplayerFrontend.trigger("apps:list", options.apps);
            }
        }
    }
});

FormplayerFrontend.on('setAppDisplayProperties', function(app) {
    FormplayerFrontend.DisplayProperties = app.profile.properties;
    if (Object.freeze) {
        Object.freeze(FormplayerFrontend.DisplayProperties);
    }
});

FormplayerFrontend.reqres.setHandler('getAppDisplayProperties', function() {
    return FormplayerFrontend.DisplayProperties || {};
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


/**
 * refreshApplication
 *
 * This takes an appId and subsequently makes a request to formplayer to
 * delete the relevant application database so that on next request
 * it gets reinstalled. On completion, navigates back to the homescreen.
 *
 * @param {String} appId - The id of the application to refresh
 */
FormplayerFrontend.on('refreshApplication', function(appId) {
    var user = FormplayerFrontend.request('currentUser'),
        formplayer_url = user.formplayer_url,
        resp,
        options = {
            url: formplayer_url + "/delete_application_dbs",
            data: JSON.stringify({
                app_id: appId,
                domain: user.domain,
                username: user.username,
            }),
        };
    Util.setCrossDomainAjaxOptions(options);
    tfLoading();
    resp = $.ajax(options);
    resp.fail(function () {
        tfLoadingComplete(true);
    }).done(function() {
        tfLoadingComplete();
        FormplayerFrontend.trigger('navigateHome', appId);
    });
});

FormplayerFrontend.on('navigateHome', function(appId) {
    var urlObject = Util.currentUrlToObject();
    urlObject.clearExceptApp();
    FormplayerFrontend.trigger("clearForm");
    FormplayerFrontend.regions.breadcrumb.empty();
    FormplayerFrontend.navigate("/single_app/" + appId, { trigger: true });
});
