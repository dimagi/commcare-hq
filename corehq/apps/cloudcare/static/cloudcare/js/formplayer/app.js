/*global Marionette, Backbone */

/**
 * The primary Marionette application managing menu navigation and launching form entry
 */

hqDefine("cloudcare/js/formplayer/app", function () {
    Marionette.setRenderer(Marionette.TemplateCache.render);
    var FormplayerFrontend = new Marionette.Application();
    var showError = hqImport('cloudcare/js/util').showError;
    var showHTMLError = hqImport('cloudcare/js/util').showHTMLError;
    var showSuccess = hqImport('cloudcare/js/util').showSuccess;
    var showWarning = hqImport('cloudcare/js/util').showWarning;
    var formplayerLoading = hqImport('cloudcare/js/util').formplayerLoading;
    var formplayerLoadingComplete = hqImport('cloudcare/js/util').formplayerLoadingComplete;
    var formplayerSyncComplete = hqImport('cloudcare/js/util').formplayerSyncComplete;
    var clearUserDataComplete = hqImport('cloudcare/js/util').clearUserDataComplete;
    var breakLocksComplete = hqImport('cloudcare/js/util').breakLocksComplete;
    var Util = hqImport("cloudcare/js/formplayer/utils/util");
    var WebFormSession = hqImport('cloudcare/js/form_entry/webformsession').WebFormSession;
    var appcues = hqImport('analytix/js/appcues');

    FormplayerFrontend.on("before:start", function (app, options) {
        // Make a get call if the csrf token isn't available when the page loads.
        if ($.cookie('XSRF-TOKEN') === undefined) {
            $.get({url: options.formplayer_url + '/serverup', global: false, xhrFields: { withCredentials: true }});
        }
        var RegionContainer = Marionette.View.extend({
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
        FormplayerFrontend.router = hqImport("cloudcare/js/formplayer/router").start();
    });

    FormplayerFrontend.navigate = function (route, options) {
        options || (options = {});
        Backbone.history.navigate(route, options);
    };

    FormplayerFrontend.getCurrentRoute = function () {
        return Backbone.history.fragment;
    };

    FormplayerFrontend.getChannel = function () {
        return Backbone.Radio.channel('formplayer');
    };

    /**
     * This function maps a jr:// media path to its HTML path IE
     * jr://images/icon/mother.png -> https://commcarehq.org/hq/multimedia/file/CommCareImage/[app_id]/mother.png
     * The actual mapping is contained in the app Couch document
     */
    FormplayerFrontend.getChannel().reply('resourceMap', function (resourcePath, appId) {
        var currentApp = FormplayerFrontend.getChannel().request("appselect:getApp", appId);
        if (!currentApp) {
            console.warn('App is undefined for app_id: ' + appId);
            console.warn('Not processing resource: ' + resourcePath);
            return;
        }
        if (resourcePath.substring(0, 7) === 'http://') {
            return resourcePath;
        } else if (!_.isEmpty(currentApp.get("multimedia_map"))) {
            var resource = currentApp.get('multimedia_map')[resourcePath];
            if (!resource) {
                console.warn('Unable to find resource ' + resourcePath + 'in multimedia map');
                return;
            }
            var id = resource.multimedia_id;
            var name = _.last(resourcePath.split('/'));
            return '/hq/multimedia/file/' + resource.media_type + '/' + id + '/' + name;
        }
    });

    FormplayerFrontend.getChannel().reply('gridPolyfillPath', function (path) {
        if (path) {
            FormplayerFrontend.gridPolyfillPath = path;
        } else {
            return FormplayerFrontend.gridPolyfillPath;
        }
    });

    FormplayerFrontend.getChannel().reply('currentUser', function () {
        if (!FormplayerFrontend.currentUser) {
            FormplayerFrontend.currentUser = hqImport("cloudcare/js/formplayer/users/models").CurrentUser();
        }
        return FormplayerFrontend.currentUser;
    });

    FormplayerFrontend.getChannel().reply('lastRecordedLocation', function () {
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

    FormplayerFrontend.getChannel().reply('clearMenu', function () {
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

    FormplayerFrontend.on('showWarning', function (message) {
        showWarning(message, $("#cloudcare-notifications"));
    });

    FormplayerFrontend.getChannel().reply('showSuccess', function (successMessage) {
        showSuccess(successMessage, $("#cloudcare-notifications"), 10000);
    });

    FormplayerFrontend.getChannel().reply('handleNotification', function (notification) {
        var type = notification.type;
        if (!type) {
            type = notification.error ? "error" : "success";
        }

        if (type === "success") {
            FormplayerFrontend.getChannel().request('showSuccess', notification.message);
        } else if (type === "warning") {
            FormplayerFrontend.trigger('showWarning', notification.message);
        } else {
            FormplayerFrontend.trigger('showError', notification.message);
        }
    });

    FormplayerFrontend.on('startForm', function (data) {
        FormplayerFrontend.getChannel().request("clearMenu");
        hqImport("cloudcare/js/formplayer/menus/util").showBreadcrumbs(data.breadcrumbs);

        data.onLoading = formplayerLoading;
        data.onLoadingComplete = formplayerLoadingComplete;
        var user = FormplayerFrontend.getChannel().request('currentUser');
        data.xform_url = user.formplayer_url;
        data.domain = user.domain;
        data.username = user.username;
        data.restoreAs = user.restoreAs;
        data.formplayerEnabled = true;
        data.displayOptions = $.extend(true, {}, user.displayOptions);
        data.onerror = function (resp) {
            var message = resp.human_readable_message || resp.exception || "Unexpected Error";
            if (resp.is_html) {
                showHTMLError(message, $("#cloudcare-notifications"));
            } else {
                showError(message, $("#cloudcare-notifications"));
            }
        };
        if (hqImport('hqwebapp/js/toggles').toggleEnabled('APP_ANALYTICS')) {
            hqImport('analytix/js/kissmetrix').track.event('Viewed Form', {
                domain: data.domain,
                name: data.title,
            });
        }
        data.onsubmit = function (resp) {
            if (resp.status === "success") {
                var $alert;
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

                if (user.environment === hqImport("cloudcare/js/formplayer/constants").PREVIEW_APP_ENVIRONMENT) {
                    hqImport('analytix/js/kissmetrix').track.event("[app-preview] User submitted a form");
                    hqImport('analytix/js/google').track.event("App Preview", "User submitted a form");
                    appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: true });
                } else if (user.environment === hqImport("cloudcare/js/formplayer/constants").WEB_APPS_ENVIRONMENT) {
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
                if (user.environment === hqImport("cloudcare/js/formplayer/constants").PREVIEW_APP_ENVIRONMENT) {
                    appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: false });
                }
                showError(resp.output, $("#cloudcare-notifications"));
            }
        };
        data.debuggerEnabled = user.debuggerEnabled;
        data.resourceMap = function (resourcePath) {
            var urlObject = Util.currentUrlToObject();
            var appId = urlObject.appId;
            return FormplayerFrontend.getChannel().request('resourceMap', resourcePath, appId);
        };
        var sess = WebFormSession(data);
        sess.renderFormXml(data, $('#webforms'));
        var notifications = hqImport('notifications/js/notifications_service_main');
        notifications.initNotifications();
        $('.menu-scrollable-container').addClass('hide');
    });

    FormplayerFrontend.on("start", function (model, options) {
        var user = FormplayerFrontend.getChannel().request('currentUser'),
            savedDisplayOptions,
            self = this;
        user.username = options.username;
        user.domain = options.domain;
        user.formplayer_url = options.formplayer_url;
        user.debuggerEnabled = options.debuggerEnabled;
        user.environment = options.environment;
        user.useLiveQuery = options.useLiveQuery;
        user.changeFormLanguage = options.changeFormLanguage;
        user.restoreAs = FormplayerFrontend.getChannel().request('restoreAsUser', user.domain, user.username);

        hqImport("cloudcare/js/formplayer/apps/api").primeApps(user.restoreAs, options.apps);

        savedDisplayOptions = _.pick(
            Util.getSavedDisplayOptions(),
            hqImport("cloudcare/js/formplayer/constants").ALLOWED_SAVED_OPTIONS
        );
        user.displayOptions = _.defaults(savedDisplayOptions, {
            singleAppMode: options.singleAppMode,
            landingPageAppMode: options.landingPageAppMode,
            phoneMode: options.phoneMode,
            oneQuestionPerScreen: options.oneQuestionPerScreen,
            language: options.language,
        });

        FormplayerFrontend.getChannel().request('gridPolyfillPath', options.gridPolyfillPath);
        $.when(FormplayerFrontend.getChannel().request("appselect:apps")).done(function (appCollection) {
            var appId;
            var apps = appCollection.toJSON();
            if (Backbone.history) {
                Backbone.history.start();
                FormplayerFrontend.regions.getRegion('restoreAsBanner').show(
                    hqImport("cloudcare/js/formplayer/users/views").RestoreAsBanner({
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
                hqImport("cloudcare/js/formplayer/hq.events").Receiver(options.allowedHost),
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
                $('.submit').prop('disabled', false);
                $('.form-control').prop('disabled', false);
            }
        );
    });

    FormplayerFrontend.on('configureDebugger', function () {
        var CloudCareDebugger = hqImport('cloudcare/js/debugger/debugger').CloudCareDebuggerMenu,
            TabIDs = hqImport('cloudcare/js/debugger/debugger').TabIDs,
            user = FormplayerFrontend.getChannel().request('currentUser'),
            cloudCareDebugger,
            $debug = $('#cloudcare-debugger');

        if (!$debug.length) {
            return;
        }

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

    FormplayerFrontend.getChannel().reply('getCurrentAppId', function () {
        // First attempt to grab app id from URL
        var urlObject = Util.currentUrlToObject(),
            user = FormplayerFrontend.getChannel().request('currentUser'),
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
        if (url.includes('single_app')) {
            return;
        }
        try {
            var options = JSON.parse(url);
            if (_.has(options, "endpointId")) {
                return;
            }
        } catch (e) {
            // do nothing
        }
        window.history.back();
    });

    FormplayerFrontend.on('setAppDisplayProperties', function (app) {
        FormplayerFrontend.DisplayProperties = app.profile.properties;
        if (Object.freeze) {
            Object.freeze(FormplayerFrontend.DisplayProperties);
        }
    });

    FormplayerFrontend.getChannel().reply('getAppDisplayProperties', function () {
        return FormplayerFrontend.DisplayProperties || {};
    });

    FormplayerFrontend.getChannel().reply('restoreAsUser', function (domain, username) {
        return hqImport("cloudcare/js/formplayer/users/utils").Users.getRestoreAsUser(
            domain,
            username
        );
    });

    // Support for workflows that require Login As before moving on to the
    // screen that the user originally requested.
    FormplayerFrontend.on('setLoginAsNextOptions', function (options) {
        FormplayerFrontend.LoginAsNextOptions = options;
        if (Object.freeze) {
            Object.freeze(FormplayerFrontend.LoginAsNextOptions);
        }
    });

    FormplayerFrontend.on('clearLoginAsNextOptions', function () {
        return FormplayerFrontend.LoginAsNextOptions = null;
    });

    FormplayerFrontend.getChannel().reply('getLoginAsNextOptions', function () {
        return FormplayerFrontend.LoginAsNextOptions || null;
    });

    /**
     * clearRestoreAsUser
     *
     * This will unset the localStorage restore as user as well as
     * unset the restore as user from the currentUser. It then
     * navigates you to the main page.
     */
    FormplayerFrontend.on('clearRestoreAsUser', function () {
        var user = FormplayerFrontend.getChannel().request('currentUser');
        hqImport("cloudcare/js/formplayer/users/utils").Users.clearRestoreAsUser(
            user.domain,
            user.username
        );
        user.restoreAs = null;
        FormplayerFrontend.regions.getRegion('restoreAsBanner').show(
            hqImport("cloudcare/js/formplayer/users/views").RestoreAsBanner({
                model: user,
            })
        );

        FormplayerFrontend.trigger('navigateHome');
    });

    FormplayerFrontend.on("sync", function () {
        var user = FormplayerFrontend.getChannel().request('currentUser'),
            username = user.username,
            domain = user.domain,
            formplayerUrl = user.formplayer_url,
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
            url: formplayerUrl + "/sync-db",
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

        var progressView = FormplayerFrontend.regions.getRegion('loadingProgress').currentView,
            retryTimeout = response.retryAfter * 1000;
        progressMessage = progressMessage || gettext('Please wait...');

        if (!progressView) {
            progressView = hqImport("cloudcare/js/formplayer/layout/views/progress_bar")({
                progressMessage: progressMessage,
            });
            FormplayerFrontend.regions.getRegion('loadingProgress').show(progressView);
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
        var progressView = FormplayerFrontend.regions.getRegion('loadingProgress').currentView,
            progressFinishTimeout = 200;

        if (progressView) {
            progressView.setProgress(1, progressFinishTimeout);
            setTimeout(function () {
                FormplayerFrontend.regions.getRegion('loadingProgress').empty();
            }, progressFinishTimeout);
        } else {
            FormplayerFrontend.regions.getRegion('loadingProgress').empty();
        }
    });


    FormplayerFrontend.on('setVersionInfo', function (versionInfo) {
        var user = FormplayerFrontend.getChannel().request('currentUser');
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
        var user = FormplayerFrontend.getChannel().request('currentUser'),
            formplayerUrl = user.formplayer_url,
            resp,
            options = {
                url: formplayerUrl + "/delete_application_dbs",
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
            if (_.has(response, 'exception')) {
                formplayerLoadingComplete(true);
                return;
            }

            formplayerLoadingComplete();
            $("#cloudcare-notifications").empty();
            FormplayerFrontend.trigger('navigateHome');
        });
    });

    /**
     * breakLocks
     *
     * Sends a request to formplayer to wipe out all application and user db for the
     * current user. Returns the ajax promise.
     */
    FormplayerFrontend.getChannel().reply('breakLocks', function () {
        var user = FormplayerFrontend.getChannel().request('currentUser'),
            formplayerUrl = user.formplayer_url,
            resp,
            options = {
                url: formplayerUrl + "/break_locks",
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
            breakLocksComplete(_.has(response, 'exception'), response.message);
        });
        return resp;
    });

    /**
     * clearUserData
     *
     * Sends a request to formplayer to wipe out all application and user db for the
     * current user. Returns the ajax promise.
     */
    FormplayerFrontend.getChannel().reply('clearUserData', function () {
        var user = FormplayerFrontend.getChannel().request('currentUser'),
            formplayerUrl = user.formplayer_url,
            resp,
            options = {
                url: formplayerUrl + "/clear_user_data",
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
            clearUserDataComplete(_.has(response, 'exception'));
        });
        return resp;
    });

    FormplayerFrontend.on('navigateHome', function () {
        // switches tab back from the application name
        document.title = gettext("Web Apps - CommCare HQ");

        var urlObject = Util.currentUrlToObject(),
            appId,
            currentUser = FormplayerFrontend.getChannel().request('currentUser');
        urlObject.clearExceptApp();
        FormplayerFrontend.regions.getRegion('breadcrumb').empty();
        if (currentUser.displayOptions.singleAppMode) {
            appId = FormplayerFrontend.getChannel().request('getCurrentAppId');
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

    return FormplayerFrontend;
});
