/*global Marionette, Backbone, WebFormSession, Util */

/**
 * The primary Marionette application managing menu navigation and launching form entry
 */

var FormplayerFrontend = new Marionette.Application();

var showError = hqImport('cloudcare/js/util').showError;
var showHTMLError = hqImport('cloudcare/js/util').showHTMLError;
var showSuccess = hqImport('cloudcare/js/util').showSuccess;
var formplayerLoading = hqImport('cloudcare/js/util').formplayerLoading;
var formplayerLoadingComplete = hqImport('cloudcare/js/util').formplayerLoadingComplete;
var formplayerSyncComplete = hqImport('cloudcare/js/util').formplayerSyncComplete;
var clearUserDataComplete = hqImport('cloudcare/js/util').clearUserDataComplete;
var appcues = hqImport('analytix/js/appcues');

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
    FormplayerFrontend.router = new FormplayerFrontend.SessionNavigate.start();
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

FormplayerFrontend.reqres.setHandler('gridPolyfillPath', function (path) {
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

FormplayerFrontend.reqres.setHandler('lastRecordedLocation', function () {
    if (!sessionStorage.locationLat) {
        return null;
    } else {
        var locationComponents = [sessionStorage.locationLat, sessionStorage.locationLon, sessionStorage.locationAltitude, sessionStorage.locationAccuracy];
        return locationComponents.join();
    }
});

FormplayerFrontend.on('clearBreadcrumbs', function () {
    $('#persistent-case-tile').html("");
});

FormplayerFrontend.on('clearForm', function () {
    $('#webforms').html("");
    $('.menu-scrollable-container').removeClass('hide');
    $('#webforms-nav').html("");
    $('#cloudcare-debugger').html("");
    $('.atwho-container').remove();
    $('#case-detail-modal').modal('hide');
});

FormplayerFrontend.reqres.setHandler('clearMenu', function () {
    $('#menu-region').html("");
});

$(document).on("ajaxStart", function () {
    $(".formplayer-request").addClass('formplayer-requester-disabled');
    formplayerLoading();
}).on("ajaxStop", function () {
    $(".formplayer-request").removeClass('formplayer-requester-disabled');
    formplayerLoadingComplete();
});

FormplayerFrontend.on('showError', function (errorMessage, isHTML) {
    if (isHTML) {
        showHTMLError(errorMessage, $("#cloudcare-notifications"));
    } else {
        showError(errorMessage, $("#cloudcare-notifications"));
    }
});

FormplayerFrontend.reqres.setHandler('showSuccess', function (successMessage) {
    showSuccess(successMessage, $("#cloudcare-notifications"), 10000);
});

FormplayerFrontend.reqres.setHandler('handleNotification', function (notification) {
    if (notification.error) {
        FormplayerFrontend.trigger('showError', notification.message);
    } else {
        FormplayerFrontend.request('showSuccess', notification.message);
    }
});

FormplayerFrontend.on('startForm', function (data) {
    FormplayerFrontend.request("clearMenu");
    FormplayerFrontend.Menus.Util.showBreadcrumbs(data.breadcrumbs);

    data.onLoading = formplayerLoading;
    data.onLoadingComplete = formplayerLoadingComplete;
    var user = FormplayerFrontend.request('currentUser');
    data.xform_url = user.formplayer_url;
    data.domain = user.domain;
    data.username = user.username;
    data.restoreAs = user.restoreAs;
    data.formplayerEnabled = true;
    data.displayOptions = $.extend(true, {}, user.displayOptions);
    data.onerror = function (resp) {
        showError(resp.human_readable_message || resp.exception, $("#cloudcare-notifications"));
    };
    data.onsubmit = function (resp) {
        if (resp.status === "success") {
            var $alert,
                isAppPreview = user.environment === FormplayerFrontend.Constants.PREVIEW_APP_ENVIRONMENT;
            if (resp.submitResponseMessage) {
                var markdowner = window.markdownit(),
                    reverse = hqImport("hqwebapp/js/initial_page_data").reverse,
                    analyticsLinks = [
                        { url: reverse('list_case_exports'), text: '[Data Feedback Loop Test] Clicked on Export Cases Link' },
                        { url: reverse('list_form_exports'), text: '[Data Feedback Loop Test] Clicked on Export Forms Link' },
                        { url: reverse('case_data', '.*'), text: '[Data Feedback Loop Test] Clicked on Case Data Link' },
                        { url: reverse('render_form_data', '.*'), text: '[Data Feedback Loop Test] Clicked on Form Data Link' },
                    ],
                    dataFeedbackLoopAnalytics = function (e) {
                        var $target = $(e.target);
                        if ($target.is("a")) {
                            var href = $target.attr("href") || '';
                            _.each(analyticsLinks, function (link) {
                                if (href.match(RegExp(link.url))) {
                                    $target.attr("target", "_blank");
                                    hqImport('analytix/js/kissmetrix').track.event(link.text);
                                }
                            });
                        }
                    };
                $("#cloudcare-notifications").off('click').on('click', dataFeedbackLoopAnalytics);
                $alert = showSuccess(markdowner.render(resp.submitResponseMessage), $("#cloudcare-notifications"), undefined, true);
            } else {
                $alert = showSuccess(gettext("Form successfully saved!"), $("#cloudcare-notifications"));
            }
            if ($alert) {
                // Clear the success notification the next time user changes screens
                var clearSuccess = function () {
                    $alert.fadeOut(500, function () {
                        $alert.remove();
                        FormplayerFrontend.off('navigation', clearSuccess);
                    });
                };
                _.delay(function () {
                    FormplayerFrontend.on('navigation', clearSuccess);
                });
            }

            if (user.environment === FormplayerFrontend.Constants.PREVIEW_APP_ENVIRONMENT) {
                hqImport('analytix/js/kissmetrix').track.event("[app-preview] User submitted a form");
                hqImport('analytix/js/google').track.event("App Preview", "User submitted a form");
                appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: true });
            } else if (user.environment === FormplayerFrontend.Constants.WEB_APPS_ENVIRONMENT) {
                hqImport('analytix/js/kissmetrix').track.event("[web apps] User submitted a form");
                hqImport('analytix/js/google').track.event("Web Apps", "User submitted a form");
                appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: true });
            }

            // After end of form nav, we want to clear everything except app and sesson id
            var urlObject = Util.currentUrlToObject();
            urlObject.onSubmit();
            Util.setUrlToObject(urlObject);

            if (resp.nextScreen !== null && resp.nextScreen !== undefined) {
                FormplayerFrontend.trigger("renderResponse", resp.nextScreen);
            } else if (urlObject.appId !== null && urlObject.appId !== undefined) {
                FormplayerFrontend.trigger("apps:currentApp");
            } else {
                FormplayerFrontend.navigate('/apps', { trigger: true });
            }
        } else {
            if (user.environment === FormplayerFrontend.Constants.PREVIEW_APP_ENVIRONMENT) {
                appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: false });
            }
            showError(resp.output, $("#cloudcare-notifications"));
        }
    };
    data.debuggerEnabled = user.debuggerEnabled;
    data.resourceMap = function (resource_path) {
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
        self = this;
    user.username = options.username;
    user.domain = options.domain;
    user.formplayer_url = options.formplayer_url;
    user.debuggerEnabled = options.debuggerEnabled;
    user.environment = options.environment;
    user.useLiveQuery = options.useLiveQuery;
    user.restoreAs = FormplayerFrontend.request('restoreAsUser', user.domain, user.username);

    FormplayerFrontend.Apps.API.primeApps(user.restoreAs, options.apps);

    savedDisplayOptions = _.pick(
        Util.getSavedDisplayOptions(),
        FormplayerFrontend.Constants.ALLOWED_SAVED_OPTIONS
    );
    user.displayOptions = _.defaults(savedDisplayOptions, {
        singleAppMode: options.singleAppMode,
        landingPageAppMode: options.landingPageAppMode,
        phoneMode: options.phoneMode,
        oneQuestionPerScreen: options.oneQuestionPerScreen,
        language: options.language,
    });

    FormplayerFrontend.request('gridPolyfillPath', options.gridPolyfillPath);
    $.when(FormplayerFrontend.request("appselect:apps")).done(function (appCollection) {
        var appId;
        var apps = appCollection.toJSON();
        if (Backbone.history) {
            Backbone.history.start();
            FormplayerFrontend.regions.restoreAsBanner.show(
                new FormplayerFrontend.Users.Views.RestoreAsBanner({
                    model: user,
                })
            );
            if (user.displayOptions.singleAppMode || user.displayOptions.landingPageAppMode) {
                appId = apps[0]['_id'];
            }

            if (self.getCurrentRoute() === "") {
                if (user.displayOptions.singleAppMode) {
                    FormplayerFrontend.trigger('setAppDisplayProperties', apps[0]);
                    FormplayerFrontend.trigger("app:singleApp", appId);
                } else if (user.displayOptions.landingPageAppMode) {
                    FormplayerFrontend.trigger('setAppDisplayProperties', apps[0]);
                    FormplayerFrontend.trigger("app:landingPageApp", appId);
                } else {
                    FormplayerFrontend.trigger("apps:list", apps);
                }
                if (user.displayOptions.phoneMode) {
                    // Refresh on start of preview mode so it ensures we're on the latest app
                    // since app updates do not work.
                    FormplayerFrontend.trigger('refreshApplication', appId);
                }
            }
        }
    });
    if (options.allowedHost) {
        window.addEventListener(
            "message",
            new FormplayerFrontend.HQ.Events.Receiver(options.allowedHost),
            false
        );
    }
    window.addEventListener(
        'offline', function () {
            showError(gettext("You are now offline. Web Apps is not optimized " +
                "for offline use. Please reconnect to the Internet before " +
                "continuing."), $("#cloudcare-notifications"));
            $('.submit').prop('disabled', 'disabled');
            $('.form-control').prop('disabled', 'disabled');
        }
    );
    window.addEventListener(
        'online', function () {
            showSuccess(gettext("You are are back online."), $("#cloudcare-notifications"));
            $('.submit').removeAttr('disabled');
            $('.form-control').removeAttr('disabled');
        }
    );
});

FormplayerFrontend.on('configureDebugger', function () {
    var CloudCareDebugger = hqImport('cloudcare/js/debugger/debugger').CloudCareDebuggerMenu,
        TabIDs = hqImport('cloudcare/js/debugger/debugger').TabIDs,
        user = FormplayerFrontend.request('currentUser'),
        cloudCareDebugger,
        $debug = $('#cloudcare-debugger');

    if (!$debug.length)
        return;

    var urlObject = Util.currentUrlToObject();
    var selections = urlObject.steps;
    var appId = urlObject.appId;

    $debug.html('');
    cloudCareDebugger = new CloudCareDebugger({
        baseUrl: user.formplayer_url,
        selections: selections,
        username: user.username,
        restoreAs: user.restoreAs,
        domain: user.domain,
        appId: appId,
        tabs: [
            TabIDs.EVAL_XPATH,
        ],
    });
    ko.cleanNode($debug[0]);
    $debug.koApplyBindings(cloudCareDebugger);
});

FormplayerFrontend.reqres.setHandler('getCurrentAppId', function () {
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

FormplayerFrontend.on('navigation:back', function () {
    var url = Backbone.history.getFragment();
    if (!url.includes('single_app')) {
        window.history.back();
    }
});

FormplayerFrontend.on('setAppDisplayProperties', function (app) {
    FormplayerFrontend.DisplayProperties = app.profile.properties;
    if (Object.freeze) {
        Object.freeze(FormplayerFrontend.DisplayProperties);
    }
});

FormplayerFrontend.reqres.setHandler('getAppDisplayProperties', function () {
    return FormplayerFrontend.DisplayProperties || {};
});

FormplayerFrontend.reqres.setHandler('restoreAsUser', function (domain, username) {
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
FormplayerFrontend.on('clearRestoreAsUser', function () {
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
        data = {
            "username": username,
            "domain": domain,
            "restoreAs": user.restoreAs,
            "useLiveQuery": user.useLiveQuery,
        },
        options;

    complete = function (response) {
        if (response.responseJSON.status === 'retry') {
            FormplayerFrontend.trigger('retry', response.responseJSON, function () {
                // Ensure that when we hit the sync db route we don't use the overwrite_cache param
                options.data = JSON.stringify($.extend(true, { preserveCache: true }, data));
                $.ajax(options);
            }, gettext('Waiting for server progress'));
        } else {
            FormplayerFrontend.trigger('clearProgress');
            formplayerSyncComplete(response.responseJSON.status === 'error');
        }
    };
    options = {
        url: formplayer_url + "/sync-db",
        data: JSON.stringify(data),
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
FormplayerFrontend.on("retry", function (response, retryFn, progressMessage) {

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

FormplayerFrontend.on('view:tablet', function () {
    $('body').addClass('preview-tablet-mode');
});

FormplayerFrontend.on('view:phone', function () {
    $('body').removeClass('preview-tablet-mode');
});

/**
 * clearProgress
 *
 * Clears the progress bar. If currently in progress, wait 200 ms to transition
 * to complete progress.
 */
FormplayerFrontend.on('clearProgress', function () {
    var progressView = FormplayerFrontend.regions.loadingProgress.currentView,
        progressFinishTimeout = 200;

    if (progressView) {
        progressView.setProgress(1, progressFinishTimeout);
        setTimeout(function () {
            FormplayerFrontend.regions.loadingProgress.empty();
        }, progressFinishTimeout);
    } else {
        FormplayerFrontend.regions.loadingProgress.empty();
    }
});


FormplayerFrontend.on('setVersionInfo', function (versionInfo) {
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
FormplayerFrontend.on('refreshApplication', function (appId) {
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
    formplayerLoading();
    resp = $.ajax(options);
    resp.fail(function () {
        formplayerLoadingComplete(true);
    }).done(function (response) {
        if (response.hasOwnProperty('exception')) {
            formplayerLoadingComplete(true);
            return;
        }

        formplayerLoadingComplete();
        $("#cloudcare-notifications").empty();
        FormplayerFrontend.trigger('navigateHome');
    });
});

/**
 * clearUserData
 *
 * Sends a request to formplayer to wipe out all application and user db for the
 * current user. Returns the ajax promise.
 */
FormplayerFrontend.reqres.setHandler('clearUserData', function () {
    var user = FormplayerFrontend.request('currentUser'),
        formplayer_url = user.formplayer_url,
        resp,
        options = {
            url: formplayer_url + "/clear_user_data",
            data: JSON.stringify({
                domain: user.domain,
                username: user.username,
                restoreAs: user.restoreAs,
            }),
        };
    Util.setCrossDomainAjaxOptions(options);
    formplayerLoading();
    resp = $.ajax(options);
    resp.fail(function () {
        formplayerLoadingComplete(true);
    }).done(function (response) {
        clearUserDataComplete(response.hasOwnProperty('exception'));
    });
    return resp;
});

FormplayerFrontend.on('navigateHome', function () {
    var urlObject = Util.currentUrlToObject(),
        appId,
        currentUser = FormplayerFrontend.request('currentUser');
    urlObject.clearExceptApp();
    FormplayerFrontend.regions.breadcrumb.empty();
    if (currentUser.displayOptions.singleAppMode) {
        appId = FormplayerFrontend.request('getCurrentAppId');
        FormplayerFrontend.trigger("app:singleApp", appId);
    } else {
        FormplayerFrontend.trigger("apps:list");
    }
});

/**
 * This is a hack to ensure that routing works properly on FireFox. Normally,
 * location.href is supposed to return a url decoded string. However, FireFox's
 * location.href returns a url encoded string. For example:
 *
 * Chrome:
 * > location.href
 * > "http://.../#{"appId"%3A"db732ce1735229da84b451cbd7cfa7ac"}"
 *
 * FireFox:
 * > location.href
 * > "http://.../#{%22appId%22%3A%22db732ce1735229da84b451cbd7cfa7ac%22}"
 *
 * This is important because BackBone caches the non url encoded fragment when you call `navigate`.
 * Then on the 'onhashchange' event, Backbone compares the cached value with the `getHash`
 * function. If they do not match it will trigger a call to loadUrl which triggers BackBone's router.
 * On FireFox, it registers as a URL change since it compares the url encoded
 * version to the url decoded version which will always mismatch. Therefore, in
 * addition to running the route through the mouseclick, the route gets run again
 * when the hash changes.
 *
 * Additional explanation here: http://stackoverflow.com/a/25849032/835696
 *
 * https://manage.dimagi.com/default.asp?250644
 */
_.extend(Backbone.History.prototype, {
    getHash: function (window) {
        var match = (window || this).location.href.match(/#(.*)$/);
        return match ? decodeURI(match[1]) : '';
    },
});
