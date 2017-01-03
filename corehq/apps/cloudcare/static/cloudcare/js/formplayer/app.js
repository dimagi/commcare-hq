/*global Marionette, Backbone, WebFormSession, Util */

/**
 * The primary Marionette application managing menu navigation and launching form entry
 */

var FormplayerFrontend = new Marionette.Application();

var showError = hqImport('cloudcare/js/util.js').showError;
var showHTMLError = hqImport('cloudcare/js/util.js').showHTMLError;
var showSuccess = hqImport('cloudcare/js/util.js').showSuccess;
var tfLoading = hqImport('cloudcare/js/util.js').tfLoading;
var tfLoadingComplete = hqImport('cloudcare/js/util.js').tfLoadingComplete;
var tfSyncComplete = hqImport('cloudcare/js/util.js').tfSyncComplete;

FormplayerFrontend.on("before:start", function () {
    var RegionContainer = Marionette.LayoutView.extend({
        el: "#menu-container",

        regions: {
            main: "#menu-region",
            loadingProgress: "#formplayer-progress-container",
            breadcrumb: "#breadcrumb-region",
            persistentCaseTile: "#persistent-case-tile",
            restoreAsBanner: '#restore-as-region',
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
        FormplayerFrontend.currentUser = new FormplayerFrontend.Users.Models.CurrentUser();
    }
    return FormplayerFrontend.currentUser;
});

FormplayerFrontend.on('clearForm', function () {
    $('#webforms').html("");
    $('.menu-scrollable-container').removeClass('hide');
    $('#webforms-nav').html("");
    $('#cloudcare-debugger').html("");
    $('.atwho-container').remove();
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

FormplayerFrontend.on('showError', function (errorMessage, isHTML) {
    if (isHTML) {
        showHTMLError(errorMessage, $("#cloudcare-notifications"));
    } else {
        showError(errorMessage, $("#cloudcare-notifications"));
    }
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
    FormplayerFrontend.Menus.Util.showBreadcrumbs(data.breadcrumbs);

    data.onLoading = tfLoading;
    data.onLoadingComplete = tfLoadingComplete;
    var user = FormplayerFrontend.request('currentUser');
    data.xform_url = user.formplayer_url;
    data.domain = user.domain;
    data.username = user.username;
    data.restoreAs = user.restoreAs;
    data.formplayerEnabled = true;
    data.displayOptions = $.extend(true, {}, user.displayOptions);
    data.onerror = function (resp) {
        showError(resp.exception, $("#cloudcare-notifications"));
    };
    data.onsubmit = function (resp) {
        if (resp.status === "success") {
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
    data.debuggerEnabled = user.debuggerEnabled;
    data.resourceMap = function(resource_path) {
        var urlObject = Util.currentUrlToObject();
        var appId = urlObject.appId;
        return FormplayerFrontend.request('resourceMap', resource_path, appId);
    };
    var sess = new WebFormSession(data);
    sess.renderFormXml(data, $('#webforms'));
    $('.menu-scrollable-container').addClass('hide');
});

FormplayerFrontend.on("start", function (options) {
    var user = FormplayerFrontend.request('currentUser'),
        savedDisplayOptions,
        appId;
    user.username = options.username;
    user.language = options.language;
    user.apps = options.apps;
    user.domain = options.domain;
    user.formplayer_url = options.formplayer_url;
    user.debuggerEnabled = options.debuggerEnabled;
    user.environment = options.environment;
    user.restoreAs = FormplayerFrontend.request('restoreAsUser', user.domain, user.username);

    savedDisplayOptions = _.pick(
        Util.getSavedDisplayOptions(),
        FormplayerFrontend.Constants.ALLOWED_SAVED_OPTIONS
    );
    user.displayOptions = _.defaults(savedDisplayOptions, {
        singleAppMode: options.singleAppMode,
        phoneMode: options.phoneMode,
        oneQuestionPerScreen: options.oneQuestionPerScreen,
    });

    FormplayerFrontend.request('gridPolyfillPath', options.gridPolyfillPath);
    if (Backbone.history) {
        Backbone.history.start();
        FormplayerFrontend.regions.restoreAsBanner.show(
            new FormplayerFrontend.Users.Views.RestoreAsBanner({
                model: user,
            })
        );
        if (user.displayOptions.singleAppMode) {
            appId = options.apps[0]['_id'];
        }

        // will be the same for every domain. TODO: get domain/username/pass from django
        if (this.getCurrentRoute() === "") {
            if (user.displayOptions.singleAppMode) {
                FormplayerFrontend.trigger('setAppDisplayProperties', options.apps[0]);
                FormplayerFrontend.trigger("app:singleApp", appId);
            } else {
                FormplayerFrontend.trigger("apps:list", options.apps);
            }
            if (user.displayOptions.phoneMode) {
                // Refresh on start of preview mode so it ensures we're on the latest app
                // since app updates do not work.
                FormplayerFrontend.trigger('refreshApplication', appId);
            }
        }
    }

    if (options.allowedHost) {
        window.addEventListener(
            "message",
            new FormplayerFrontend.HQ.Events.Receiver(options.allowedHost),
            false
        );
    }
});

FormplayerFrontend.reqres.setHandler('getCurrentAppId', function() {
    // First attempt to grab app id from URL
    var urlObject = Util.currentUrlToObject(),
        user = FormplayerFrontend.request('currentUser'),
        appId;

    appId = urlObject.appId;

    if (appId) {
        return appId;
    }

    // If it's not in the URL, then we are either on the home screen of formplayer
    // and there is no app selected, or we are in preview mode.
    appId = user.previewAppId;

    return appId || null;
});

FormplayerFrontend.on('navigation:back', function() {
    var url = Backbone.history.getFragment();
    if (!url.includes('single_app')) {
        window.history.back();
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

FormplayerFrontend.reqres.setHandler('restoreAsUser', function(domain, username) {
    return FormplayerFrontend.Utils.Users.getRestoreAsUser(
        domain,
        username
    );
});

/**
 * clearRestoreAsUser
 *
 * This will unset the localStorage restore as user as well as
 * unset the restore as user from the currentUser. It then
 * navigates you to the main page.
 */
FormplayerFrontend.on('clearRestoreAsUser', function() {
    var user = FormplayerFrontend.request('currentUser'),
        appId;
    FormplayerFrontend.Utils.Users.clearRestoreAsUser(
        user.domain,
        user.username
    );
    user.restoreAs = null;
    FormplayerFrontend.regions.restoreAsBanner.show(
        new FormplayerFrontend.Users.Views.RestoreAsBanner({
            model: user,
        })
    );

    FormplayerFrontend.trigger('navigateHome');
});

FormplayerFrontend.on("sync", function () {
    var user = FormplayerFrontend.request('currentUser'),
        username = user.username,
        domain = user.domain,
        formplayer_url = user.formplayer_url,
        complete,
        options;

    complete = function(response) {
        if (response.responseJSON.status === 'retry') {
            FormplayerFrontend.trigger('retry', response.responseJSON, function() {
                $.ajax(options);
            }, gettext('Waiting for server progress'));
        } else {
            FormplayerFrontend.trigger('clearProgress');
            tfSyncComplete(response.responseJSON.status === 'error');
        }
    };
    options = {
        url: formplayer_url + "/sync-db",
        data: JSON.stringify({
            "username": username,
            "domain": domain,
            "restoreAs": user.restoreAs,
        }),
        complete: complete,
    };
    Util.setCrossDomainAjaxOptions(options);
    $.ajax(options);
});

/**
 * retry
 *
 * Will retry a restore when doing an async restore.
 *
 * @param {Object} response - An async restore response object
 * @param {function} retryFn - The function to be called when ready to retry restoring
 * @param {String} progressMessage - The message to be displayed above the progress bar
 */
FormplayerFrontend.on("retry", function(response, retryFn, progressMessage) {

    var progressView = FormplayerFrontend.regions.loadingProgress.currentView,
        retryTimeout = response.retryAfter * 1000;
    progressMessage = progressMessage || gettext('Please wait...');

    if (!progressView) {
        progressView = new FormplayerFrontend.Layout.Views.ProgressView({
            progressMessage: progressMessage,
        });
        FormplayerFrontend.regions.loadingProgress.show(progressView);
    }

    progressView.setProgress(response.done, response.total, retryTimeout);
    setTimeout(retryFn, retryTimeout);
});

FormplayerFrontend.on('view:tablet', function() {
    $('body').addClass('preview-tablet-mode');
});

FormplayerFrontend.on('view:phone', function() {
    $('body').removeClass('preview-tablet-mode');
});

/**
 * clearProgress
 *
 * Clears the progress bar. If currently in progress, wait 200 ms to transition
 * to complete progress.
 */
FormplayerFrontend.on('clearProgress', function() {
    var progressView = FormplayerFrontend.regions.loadingProgress.currentView,
        progressFinishTimeout = 0;
    if (progressView) {
        progressFinishTimeout = 200;
        progressView.setProgress(1, progressFinishTimeout);
    }

    setTimeout(function() {
        FormplayerFrontend.regions.loadingProgress.empty();
    }, progressFinishTimeout);
});


FormplayerFrontend.on('setVersionInfo', function(versionInfo) {
    var user = FormplayerFrontend.request('currentUser');
    $("#version-info").text(versionInfo || '');
    if (versionInfo) {
        user.set('versionInfo',  versionInfo);
    }
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
    if (!appId) {
        throw new Error('Attempt to refresh application for null appId');
    }
    var user = FormplayerFrontend.request('currentUser'),
        formplayer_url = user.formplayer_url,
        resp,
        options = {
            url: formplayer_url + "/delete_application_dbs",
            data: JSON.stringify({
                app_id: appId,
                domain: user.domain,
                username: user.username,
                restoreAs: user.restoreAs,
            }),
        };
    Util.setCrossDomainAjaxOptions(options);
    tfLoading();
    resp = $.ajax(options);
    resp.fail(function () {
        tfLoadingComplete(true);
    }).done(function() {
        tfLoadingComplete();
        $("#cloudcare-notifications").empty();
        FormplayerFrontend.trigger('navigateHome');
    });
});

FormplayerFrontend.on('navigateHome', function() {
    var urlObject = Util.currentUrlToObject(),
        appId,
        currentUser = FormplayerFrontend.request('currentUser');
    urlObject.clearExceptApp();
    FormplayerFrontend.regions.breadcrumb.empty();
    if (currentUser.displayOptions.singleAppMode) {
        appId = FormplayerFrontend.request('getCurrentAppId');
        FormplayerFrontend.navigate("/single_app/" + appId, { trigger: true });
    } else {
        FormplayerFrontend.navigate("/apps", { trigger: true });
    }
});
