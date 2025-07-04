/**
 * The primary Marionette application managing menu navigation and launching form entry
 */
define("cloudcare/js/formplayer/app", [
    'jquery',
    'knockout',
    'underscore',
    'backbone',
    'backbone.marionette',
    'markdown-it/dist/markdown-it',
    'bootstrap5',
    'hqwebapp/js/initial_page_data',
    'analytix/js/google',
    'analytix/js/noopMetrics',
    'cloudcare/js/utils',
    'cloudcare/js/formplayer/apps/api',
    'cloudcare/js/formplayer/constants',
    'cloudcare/js/formplayer/utils/utils',
    'cloudcare/js/formplayer/layout/views/progress_bar',
    'cloudcare/js/formplayer/users/models',
    'cloudcare/js/form_entry/web_form_session',
    'marionette.templatecache/lib/marionette.templatecache.min',    // needed for Marionette.TemplateCache
    'cloudcare/js/gtx',
    'backbone.radio',
    'jquery.cookie/jquery.cookie',  // $.cookie
], function (
    $,
    ko,
    _,
    Backbone,
    Marionette,
    markdowner,
    bootstrap,
    initialPageData,
    GGAnalytics,
    noopMetrics,
    CloudcareUtils,
    AppsAPI,
    Const,
    FormplayerUtils,
    ProgressBar,
    UsersModels,
    WebFormSession,
    TemplateCache,
    gtx,
) {
    Marionette.setRenderer(TemplateCache.render);

    const WebApp = Marionette.Application.extend({
        getXSRF: function (options) {
            return $.get({
                url: options.formplayer_url + '/serverup',
                global: false, xhrFields: {withCredentials: true},
            });
        },
    });

    const FormplayerFrontend = new WebApp();

    FormplayerFrontend.on("before:start", function () {
        if (!FormplayerFrontend.regions) {
            FormplayerFrontend.regions = CloudcareUtils.getRegionContainer();
        }
        import("cloudcare/js/formplayer/router").then(function (Router) {
            FormplayerFrontend.router = Router.start();
        });
    });

    FormplayerFrontend.getCurrentRoute = function () {
        return Backbone.history.fragment;
    };

    FormplayerFrontend.getChannel = function () {
        return Backbone.Radio.channel('formplayer');
    };

    FormplayerFrontend.getRegion = function (region) {
        if (!FormplayerFrontend.regions) {
            FormplayerFrontend.regions = CloudcareUtils.getRegionContainer();
        }
        return FormplayerFrontend.regions.getRegion(region);
    };

    FormplayerFrontend.confirmUserWantsToNavigateAwayFromForm = function () {
        if (FormplayerFrontend.unsavedFormInProgress) {
            const userConfirmedYes = window.confirm(gettext("You have a form in progress. Are you sure you want to navigate away?"));
            if (!userConfirmedYes) {
                return false;
            }
        }
        FormplayerFrontend.trigger('setUnsavedFormNotInProgress');
        return true;
    };

    FormplayerFrontend.showRestoreAs = function (user) {
        import("cloudcare/js/formplayer/users/views").then(function (UsersViews) {
            FormplayerFrontend.regions.getRegion('restoreAsBanner').show(
                UsersViews.RestoreAsBanner({model: user, smallScreen: false}));
            const mobileRegion = FormplayerFrontend.regions.getRegion('mobileRestoreAsBanner');
            if (mobileRegion.$el.length) {      // This region doesn't exist in app preview
                mobileRegion.show(UsersViews.RestoreAsBanner({model: user, smallScreen: true}));
            }
        });
    };

    /**
     * This function maps a jr:// media path to its HTML path IE
     * jr://images/icon/mother.png -> https://commcarehq.org/hq/multimedia/file/CommCareImage/[app_id]/mother.png
     * The actual mapping is contained in the app Couch document
     */
    FormplayerFrontend.getChannel().reply('resourceMap', function (resourcePath, appId) {
        var currentApp = AppsAPI.getAppEntity(appId);
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
        FormplayerFrontend.trigger('setUnsavedFormNotInProgress');
        $('#webforms').html("");
        $('.menu-scrollable-container').removeClass("d-none");
        $('#sidebar-and-content').removeClass('remove-margins-on-mobile');
        $('#webforms-nav').html("");
        $('#cloudcare-debugger').html("");
        $('#cloudcare-main').removeClass('has-debugger');
        $('.atwho-container').remove();
        bootstrap.Modal.getOrCreateInstance($('#case-detail-modal')).hide();
        sessionStorage.removeItem('collapsedIx');
    });

    FormplayerFrontend.getChannel().reply('clearMenu', function () {
        $('#menu-region').html("");
        $('#sidebar-region').html("");
    });

    $(document).on("ajaxStart", function () {
        $(".formplayer-request").addClass('formplayer-requester-disabled');
        CloudcareUtils.formplayerLoading();
    }).on("ajaxStop", function () {
        $(".formplayer-request").removeClass('formplayer-requester-disabled');
        CloudcareUtils.formplayerLoadingComplete();
    });

    FormplayerFrontend.on('clearNotifications', function () {
        $("#cloudcare-notifications").empty();
    });

    FormplayerFrontend.on('showError', function (errorMessage, isHTML, reportToHq, additionalData) {
        if (isHTML) {
            CloudcareUtils.showHTMLError(errorMessage, $("#cloudcare-notifications"), null, reportToHq);
        } else {
            CloudcareUtils.showError(errorMessage, $("#cloudcare-notifications"), reportToHq, additionalData);
        }
    });

    FormplayerFrontend.on('showWarning', function (message) {
        CloudcareUtils.showWarning(message, $("#cloudcare-notifications"));
    });

    FormplayerFrontend.on('showSuccess', function (successMessage) {
        CloudcareUtils.showSuccess(successMessage, $("#cloudcare-notifications"), 10000);
    });

    FormplayerFrontend.on('handleNotification', function (notification) {
        var type = notification.type;
        if (!type) {
            type = notification.error ? "error" : "success";
        }

        if (type === "success") {
            FormplayerFrontend.trigger('showSuccess', notification.message);
        } else if (type === "warning") {
            FormplayerFrontend.trigger('showWarning', notification.message);
        } else {
            FormplayerFrontend.trigger('showError', notification.message);
        }
    });

    FormplayerFrontend.on('startForm', function (data) {
        FormplayerFrontend.permitIntervalSync = false;
        FormplayerFrontend.getChannel().request("clearMenu");

        data.onLoading = CloudcareUtils.formplayerLoading;
        data.onLoadingComplete = CloudcareUtils.formplayerLoadingComplete;
        var user = UsersModels.getCurrentUser();
        data.xform_url = user.formplayer_url;
        data.domain = user.domain;
        data.username = user.username;
        data.restoreAs = user.restoreAs;
        data.formplayerEnabled = true;
        data.displayOptions = $.extend(true, {}, user.displayOptions);
        data.onerror = function (resp) {
            var message = resp.human_readable_message || resp.exception;
            if (!message && resp.notification && resp.notification.message) {
                message = resp.notification.message;
            }
            if (resp.is_html) {
                CloudcareUtils.showHTMLError(message, $("#cloudcare-notifications"), null, resp.reportToHq);
            } else {
                CloudcareUtils.showError(message, $("#cloudcare-notifications"), resp.reportToHq);
            }
        };
        noopMetrics.track.event('Viewed Form', {
            domain: data.domain,
            name: data.title,
        });
        gtx.logStartForm(data.title);
        data.onsubmit = function (resp) {
            if (resp.status === "success") {
                var $alert;
                if (resp.submitResponseMessage) {
                    var analyticsLinks = [
                            { url: initialPageData.reverse('list_case_exports'), text: '[Data Feedback Loop Test] Clicked on Export Cases Link' },
                            { url: initialPageData.reverse('list_form_exports'), text: '[Data Feedback Loop Test] Clicked on Export Forms Link' },
                            { url: initialPageData.reverse('case_data', '.*'), text: '[Data Feedback Loop Test] Clicked on Case Data Link' },
                            { url: initialPageData.reverse('render_form_data', '.*'), text: '[Data Feedback Loop Test] Clicked on Form Data Link' },
                        ],
                        dataFeedbackLoopAnalytics = function (e) {
                            var $target = $(e.target);
                            if ($target.is("a")) {
                                var href = $target.attr("href") || '';
                                _.each(analyticsLinks, function (link) {
                                    if (href.match(RegExp(link.url))) {
                                        $target.attr("target", "_blank");
                                        noopMetrics.track.event(link.text);
                                    }
                                });
                            }
                        };
                    $("#cloudcare-notifications").off('click').on('click', dataFeedbackLoopAnalytics);
                    $alert = CloudcareUtils.showSuccess(markdowner().render(resp.submitResponseMessage), $("#cloudcare-notifications"), undefined, true);
                } else {
                    $alert = CloudcareUtils.showSuccess(gettext("Form successfully saved!"), $("#cloudcare-notifications"));
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

                if (user.isAppPreview) {
                    noopMetrics.track.event("[app-preview] User submitted a form");
                    GGAnalytics.track.event("App Preview", "User submitted a form");
                } else if (user.environment === Const.WEB_APPS_ENVIRONMENT) {
                    noopMetrics.track.event("[web apps] User submitted a form");
                    GGAnalytics.track.event("Web Apps", "User submitted a form");
                }

                // After end of form nav, we want to clear everything except app and sesson id
                var urlObject = FormplayerUtils.currentUrlToObject();
                urlObject.onSubmit();
                FormplayerUtils.setUrlToObject(urlObject);

                if (resp.nextScreen !== null && resp.nextScreen !== undefined) {
                    if (resp.nextScreen.session_id) {
                        FormplayerUtils.doUrlAction((urlObject) => {
                            urlObject.sessionId = resp.nextScreen.session_id;
                        }, true);
                    }
                    FormplayerFrontend.trigger("renderResponse", resp.nextScreen);
                } else if (urlObject.appId !== null && urlObject.appId !== undefined) {
                    FormplayerFrontend.trigger("apps:currentApp");
                } else {
                    FormplayerUtils.navigate('/apps', { trigger: true });
                }
            } else {
                CloudcareUtils.showError(resp.output, $("#cloudcare-notifications"));
            }
        };
        data.debuggerEnabled = user.debuggerEnabled;
        data.resourceMap = function (resourcePath) {
            var urlObject = FormplayerUtils.currentUrlToObject();
            var appId = urlObject.appId;
            return FormplayerFrontend.getChannel().request('resourceMap', resourcePath, appId);
        };
        var sess = WebFormSession.WebFormSession(data);
        sess.renderFormXml(data, $('#webforms'));
        $('.menu-scrollable-container').addClass("d-none");
        $('#sidebar-and-content').addClass('remove-margins-on-mobile');
    });

    FormplayerFrontend.on("start", function (model, options) {
        var self = this,
            user = UsersModels.setCurrentUser(options);

        import("cloudcare/js/formplayer/users/utils").then(function () {   // restoreAsUser
            user.restoreAs = FormplayerFrontend.getChannel().request('restoreAsUser', user.domain, user.username);
            AppsAPI.primeApps(user.restoreAs, options.apps);
        });

        import("cloudcare/js/formplayer/router").then(function (Router) {
            FormplayerFrontend.router = Router.start();
            $.when(AppsAPI.getAppEntities()).done(function (appCollection) {
                var appId;
                var apps = appCollection.toJSON();
                if (Backbone.history) {
                    Backbone.history.start();
                    FormplayerFrontend.showRestoreAs(user);
                    if (user.displayOptions.singleAppMode) {
                        appId = apps[0]['_id'];
                    }

                    if (self.getCurrentRoute() === "") {
                        if (user.displayOptions.singleAppMode) {
                            FormplayerFrontend.trigger('setAppDisplayProperties', apps[0]);
                            FormplayerFrontend.trigger("app:singleApp", appId);
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
        });

        if (options.allowedHost) {
            import("cloudcare/js/formplayer/hq_events").then(function (HQEvents) {
                window.addEventListener(
                    "message",
                    HQEvents.Receiver(options.allowedHost),
                    false,
                );
            });
        }

        const reconnectTimingWindow = 2000;
        let offlineTime;

        window.addEventListener(
            'offline',function () {
                offlineTime = new Date();
                _.delay(function () {
                    if (!this.navigator.onLine && (new Date() - offlineTime) > reconnectTimingWindow) {
                        CloudcareUtils.showError(gettext("You are now offline. Web Apps is not optimized " +
                            "for offline use. Please reconnect to the Internet before " +
                            "continuing."), $("#cloudcare-notifications"));
                        $('.submit').prop('disabled', 'disabled');
                        $('.form-control, .form-select').prop('disabled', 'disabled');
                    }
                },reconnectTimingWindow);
            });

        window.addEventListener(
            'online', function () {
                if ((new Date() - offlineTime) > reconnectTimingWindow) {
                    CloudcareUtils.showSuccess(gettext("You are are back online."), $("#cloudcare-notifications"));
                    $('.submit').prop('disabled', false);
                    $('.form-control, .form-select').prop('disabled', false);
                }
            },
        );

        window.addEventListener(
            'beforeprint', function () {
                $('.card, .q').last().addClass('last');
            },
        );

        window.addEventListener(
            'afterprint', function () {
                $('.last').removeClass('last');
            },
        );
    });

    FormplayerFrontend.on('configureDebugger', function () {
        import("cloudcare/js/debugger/debugger").then(function (Debugger) {
            var CloudCareDebugger = Debugger.CloudCareDebuggerMenu,
                TabIDs = Debugger.TabIDs,
                user = UsersModels.getCurrentUser(),
                cloudCareDebugger,
                $debug = $('#cloudcare-debugger');

            if (!$debug.length) {
                return;
            }

            var urlObject = FormplayerUtils.currentUrlToObject();

            $debug.html('');
            cloudCareDebugger = new CloudCareDebugger({
                baseUrl: user.formplayer_url,
                selections: urlObject.selections,
                queryData: urlObject.queryData,
                username: user.username,
                restoreAs: user.restoreAs,
                domain: user.domain,
                appId: urlObject.appId,
                tabs: [
                    TabIDs.EVAL_XPATH,
                ],
            });
            ko.cleanNode($debug[0]);
            $debug.koApplyBindings(cloudCareDebugger);
        });
    });

    FormplayerFrontend.getChannel().reply('getCurrentAppId', function () {
        // First attempt to grab app id from URL
        var urlObject = FormplayerUtils.currentUrlToObject(),
            user = UsersModels.getCurrentUser(),
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

    // Support for workflows that require Log In As before moving on to the
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

    function makeSyncRequest(route, requestData) {
        var options,
            complete,
            user = UsersModels.getCurrentUser(),
            formplayerUrl = user.formplayer_url,
            data = {
                "username": user.username,
                "domain": user.domain,
                "restoreAs": user.restoreAs,
            };

        if (requestData) {
            data = $.extend(data, requestData);
        }

        complete = function (response) {
            if (route === "sync-db") {
                if (response.responseJSON.status === 'retry') {
                    FormplayerFrontend.trigger('retry', response.responseJSON, function () {
                        // Ensure that when we hit the sync db route we don't use the overwrite_cache param
                        options.data = JSON.stringify($.extend(true, { preserveCache: true }, data));
                        $.ajax(options);
                    }, gettext('Waiting for server progress'));
                } else {
                    FormplayerFrontend.trigger('clearProgress');
                    CloudcareUtils.formplayerSyncComplete(response.responseJSON.status === 'error');
                }
            } else if (route === "interval_sync-db") {
                if (response.status === 'retry') {
                    FormplayerFrontend.trigger('retry', response, function () {
                        options.data = JSON.stringify($.extend({mustRestore: true}, data));
                        $.ajax(options);
                    }, gettext('Waiting for server progress'));
                } else {
                    FormplayerFrontend.trigger('clearProgress');
                }
            }
        };

        options = {
            url: formplayerUrl + "/" + route,
            data: JSON.stringify(data),
            complete: complete,
        };
        FormplayerUtils.setCrossDomainAjaxOptions(options);
        $.ajax(options);
    }
    FormplayerFrontend.on("sync", function () {
        makeSyncRequest("sync-db");
    });

    FormplayerFrontend.on("interval_sync-db", function (appId) {
        makeSyncRequest("interval_sync-db", {"app_id": appId});
    });

    FormplayerFrontend.on("startSyncInterval", function (delayInMilliseconds) {
        function shouldSync() {
            const currentTime = Date.now(),
                lastUserActivityTime =  sessionStorage.getItem("lastUserActivityTime") || 0,
                elapsedTimeSinceLastActivity = currentTime - lastUserActivityTime,
                isInApp = FormplayerUtils.currentUrlToObject().appId !== undefined;
            if (elapsedTimeSinceLastActivity <= delayInMilliseconds && isInApp) {
                return true;
            }
        }

        if (!FormplayerFrontend.syncInterval) {
            FormplayerFrontend.syncInterval = setInterval(function () {
                const urlObject = FormplayerUtils.currentUrlToObject(),
                    currentApp = AppsAPI.getAppEntity(urlObject.appId);
                let customProperties = {};
                if (currentApp && currentApp.attributes && currentApp.attributes.profile) {
                    customProperties = currentApp.attributes.profile.custom_properties || {};
                }
                const useAggressiveSyncTiming = (customProperties[Const.POST_FORM_SYNC] === "yes");
                if (!useAggressiveSyncTiming) {
                    FormplayerFrontend.trigger("stopSyncInterval");
                }
                if (shouldSync() && FormplayerFrontend.permitIntervalSync) {
                    FormplayerFrontend.trigger("interval_sync-db", urlObject.appId);
                }
            }, delayInMilliseconds);
        }
    });

    FormplayerFrontend.on("stopSyncInterval", function () {
        clearInterval(FormplayerFrontend.syncInterval);
        FormplayerFrontend.syncInterval = null;
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
            progressView = ProgressBar({
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

        if (progressView && progressView.hasProgress()) {
            progressView.setProgress(1, 1, progressFinishTimeout);
            setTimeout(function () {
                FormplayerFrontend.regions.getRegion('loadingProgress').empty();
            }, progressFinishTimeout);
        } else {
            FormplayerFrontend.regions.getRegion('loadingProgress').empty();
        }
    });


    FormplayerFrontend.on('setVersionInfo', function (versionInfo) {
        var user = UsersModels.getCurrentUser();
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
        var user = UsersModels.getCurrentUser(),
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
        FormplayerUtils.setCrossDomainAjaxOptions(options);
        CloudcareUtils.formplayerLoading();
        resp = $.ajax(options);
        resp.fail(function () {
            CloudcareUtils.formplayerLoadingComplete(true);
        }).done(function (response) {
            if (_.has(response, 'exception')) {
                CloudcareUtils.formplayerLoadingComplete(true);
                return;
            }

            CloudcareUtils.formplayerLoadingComplete();
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
        var user = UsersModels.getCurrentUser(),
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
        FormplayerUtils.setCrossDomainAjaxOptions(options);
        CloudcareUtils.formplayerLoading();
        resp = $.ajax(options);
        resp.fail(function () {
            CloudcareUtils.formplayerLoadingComplete(true);
        }).done(function (response) {
            CloudcareUtils.breakLocksComplete(_.has(response, 'exception'), response.message);
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
        var user = UsersModels.getCurrentUser(),
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
        FormplayerUtils.setCrossDomainAjaxOptions(options);
        CloudcareUtils.formplayerLoading();
        resp = $.ajax(options);
        resp.fail(function () {
            CloudcareUtils.formplayerLoadingComplete(true);
        }).done(function (response) {
            CloudcareUtils.clearUserDataComplete(_.has(response, 'exception'));
        });
        return resp;
    });

    FormplayerFrontend.on('navigateHome', function () {
        // switches tab back from the application name
        document.title = gettext("Web Apps - CommCare HQ");

        var urlObject = FormplayerUtils.currentUrlToObject(),
            appId,
            currentUser = UsersModels.getCurrentUser();
        urlObject.clearExceptApp();
        FormplayerFrontend.regions.getRegion('sidebar').empty();
        FormplayerFrontend.regions.getRegion('breadcrumb').empty();
        FormplayerFrontend.regions.getRegion('persistentMenu').empty();
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

    FormplayerFrontend.on("setUnsavedFormInProgress", function () {
        FormplayerFrontend.unsavedFormInProgress = true;
        window.onbeforeunload = function () {
            return true;
        };
    });

    FormplayerFrontend.on("setUnsavedFormNotInProgress", function () {
        if (FormplayerFrontend.unsavedFormInProgress) {
            FormplayerFrontend.unsavedFormInProgress = false;
            window.onbeforeunload = null;
        }
    });

    return FormplayerFrontend;
});
