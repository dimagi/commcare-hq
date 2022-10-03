'use strict';
/*global Marionette, Backbone */

/**
 * The primary Marionette application managing menu navigation and launching form entry
 */

hqDefine("cloudcare/js/formplayer/app", function () {
    var appcues = hqImport('analytix/js/appcues'),
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        CloudcareUtils = hqImport("cloudcare/js/utils"),
        Const = hqImport("cloudcare/js/formplayer/constants"),
        FormplayerUtils = hqImport("cloudcare/js/formplayer/utils/utils"),
        GGAnalytics = hqImport("analytix/js/google"),
        Kissmetrics = hqImport("analytix/js/kissmetrix"),
        ProgressBar = hqImport("cloudcare/js/formplayer/layout/views/progress_bar"),
        UsersModels = hqImport("cloudcare/js/formplayer/users/models"),
        WebFormSession = hqImport('cloudcare/js/form_entry/web_form_session');

    Marionette.setRenderer(Marionette.TemplateCache.render);
    var FormplayerFrontend = new Marionette.Application();

    FormplayerFrontend.on("before:start", function (app, options) {
        const xsrfRequest = new $.Deferred();
        this.xsrfRequest = xsrfRequest.promise();
        // Make a get call if the csrf token isn't available when the page loads.
        if ($.cookie('XSRF-TOKEN') === undefined) {
            $.get(
                {url: options.formplayer_url + '/serverup', global: false, xhrFields: { withCredentials: true }}
            ).always(() => { xsrfRequest.resolve(); });
        } else {
            // resolve immediately
            xsrfRequest.resolve();
        }

        if (!FormplayerFrontend.regions) {
            FormplayerFrontend.regions = CloudcareUtils.getRegionContainer();
        }
        let sidebar = FormplayerFrontend.regions.getRegion('sidebar');
        sidebar.on('show', function () {
            $('#content-container').addClass('full-width');
            $('#menu-region').addClass('sidebar-push');
        });
        sidebar.on('hide empty', function () {
            $('#content-container').removeClass('full-width');
            $('#menu-region').removeClass('sidebar-push');
        });

        hqRequire(["cloudcare/js/formplayer/router"], function (Router) {
            FormplayerFrontend.router = Router.start();
        });
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
                console.warn('Unable to find resource ' + resourcePath + ' in multimedia map');
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
            FormplayerFrontend.currentUser = UsersModels.CurrentUser();
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

    FormplayerFrontend.on('showError', function (errorMessage, isHTML, reportToHq) {
        if (isHTML) {
            CloudcareUtils.showHTMLError(errorMessage, $("#cloudcare-notifications"), null, reportToHq);
        } else {
            CloudcareUtils.showError(errorMessage, $("#cloudcare-notifications"), reportToHq);
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
        FormplayerFrontend.getChannel().request("clearMenu");
        hqRequire(["cloudcare/js/formplayer/menus/utils"], function (MenusUtils) {
            MenusUtils.showBreadcrumbs(data.breadcrumbs);
        });

        data.onLoading = CloudcareUtils.formplayerLoading;
        data.onLoadingComplete = CloudcareUtils.formplayerLoadingComplete;
        var user = FormplayerFrontend.getChannel().request('currentUser');
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
        Kissmetrics.track.event('Viewed Form', {
            domain: data.domain,
            name: data.title,
        });
        data.onsubmit = function (resp) {
            if (resp.status === "success") {
                var $alert;
                if (resp.submitResponseMessage) {
                    var markdowner = window.markdownit(),
                        analyticsLinks = [
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
                                        Kissmetrics.track.event(link.text);
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

                if (user.environment === Const.PREVIEW_APP_ENVIRONMENT) {
                    Kissmetrics.track.event("[app-preview] User submitted a form");
                    GGAnalytics.track.event("App Preview", "User submitted a form");
                    appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: true });
                } else if (user.environment === Const.WEB_APPS_ENVIRONMENT) {
                    Kissmetrics.track.event("[web apps] User submitted a form");
                    GGAnalytics.track.event("Web Apps", "User submitted a form");
                    appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: true });
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
                    FormplayerFrontend.navigate('/apps', { trigger: true });
                }
            } else {
                if (user.environment === Const.PREVIEW_APP_ENVIRONMENT) {
                    appcues.trackEvent(appcues.EVENT_TYPES.FORM_SUBMIT, { success: false });
                }
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
        if (user.environment === Const.WEB_APPS_ENVIRONMENT) {
            // This isn't a circular import, but importing it at the top level would
            // mean it would need to be faked for tests
            hqRequire(["notifications/js/bootstrap3/notifications_service_main"], function (Notifications) {
                Notifications.initNotifications();
            });
        }
        $('.menu-scrollable-container').addClass('hide');
    });

    FormplayerFrontend.on("start", function (model, options) {
        var user = FormplayerFrontend.getChannel().request('currentUser'),
            self = this;
        user.username = options.username;
        user.domain = options.domain;
        user.formplayer_url = options.formplayer_url;
        user.debuggerEnabled = options.debuggerEnabled;
        user.environment = options.environment;
        user.restoreAs = FormplayerFrontend.getChannel().request('restoreAsUser', user.domain, user.username);

        hqRequire(["cloudcare/js/formplayer/apps/api"], function (AppsAPI) {
            AppsAPI.primeApps(user.restoreAs, options.apps);
        });
        $.when(FormplayerUtils.getSavedDisplayOptions()).done(function (savedDisplayOptions) {
            savedDisplayOptions = _.pick(
                savedDisplayOptions,
                Const.ALLOWED_SAVED_OPTIONS
            );
            user.displayOptions = _.defaults(savedDisplayOptions, {
                singleAppMode: options.singleAppMode,
                landingPageAppMode: options.landingPageAppMode,
                phoneMode: options.phoneMode,
                oneQuestionPerScreen: options.oneQuestionPerScreen,
                language: options.language,
            });

            FormplayerFrontend.getChannel().request('gridPolyfillPath', options.gridPolyfillPath);
            $.when(
                FormplayerFrontend.getChannel().request("appselect:apps"),
                FormplayerFrontend.xsrfRequest
            ).done(function (appCollection) {
                var appId;
                var apps = appCollection.toJSON();
                if (Backbone.history) {
                    Backbone.history.start();
                    hqRequire(["cloudcare/js/formplayer/users/views"], function (UsersViews) {
                        FormplayerFrontend.regions.getRegion('restoreAsBanner').show(
                            UsersViews.RestoreAsBanner({
                                model: user,
                            })
                        );
                    });
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
        });

        if (options.allowedHost) {
            hqRequire(["cloudcare/js/formplayer/hq_events"], function (HQEvents) {
                window.addEventListener(
                    "message",
                    HQEvents.Receiver(options.allowedHost),
                    false
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
                        $('.form-control').prop('disabled', 'disabled');
                    }
                },reconnectTimingWindow);
            });

        window.addEventListener(
            'online', function () {
                if ((new Date() - offlineTime) > reconnectTimingWindow) {
                    CloudcareUtils.showSuccess(gettext("You are are back online."), $("#cloudcare-notifications"));
                    $('.submit').prop('disabled', false);
                    $('.form-control').prop('disabled', false);
                }
            }
        );

        window.addEventListener(
            'beforeprint', function () {
                $('.panel.panel-default, .q.form-group').last().addClass('last');
            }
        );

        window.addEventListener(
            'afterprint', function () {
                $('.last').removeClass('last');
            }
        );
    });

    FormplayerFrontend.on('configureDebugger', function () {
        hqRequire(["cloudcare/js/debugger/debugger"], function (Debugger) {
            var CloudCareDebugger = Debugger.CloudCareDebuggerMenu,
                TabIDs = Debugger.TabIDs,
                user = FormplayerFrontend.getChannel().request('currentUser'),
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
                CloudcareUtils.formplayerSyncComplete(response.responseJSON.status === 'error');
            }
        };
        options = {
            url: formplayerUrl + "/sync-db",
            data: JSON.stringify(data),
            complete: complete,
        };
        FormplayerUtils.setCrossDomainAjaxOptions(options);
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
            currentUser = FormplayerFrontend.getChannel().request('currentUser');
        urlObject.clearExceptApp();
        FormplayerFrontend.regions.getRegion('sidebar').empty();
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
