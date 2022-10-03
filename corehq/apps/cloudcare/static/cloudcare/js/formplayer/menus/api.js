'use strict';
/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */
hqDefine("cloudcare/js/formplayer/menus/api", [
    'jquery',
    'underscore',
    'sentry_browser',
    'hqwebapp/js/initial_page_data',
    'cloudcare/js/formplayer/menus/collections',
    'cloudcare/js/formplayer/constants',
    'cloudcare/js/form_entry/errors',
    'cloudcare/js/form_entry/utils',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/utils/utils',
    'cloudcare/js/formplayer/layout/views/progress_bar',
], function (
    $,
    _,
    Sentry,
    initialPageData,
    Collections,
    constants,
    errors,
    formEntryUtils,
    FormplayerFrontend,
    formplayerUtils,
    ProgressBar
) {
    var API = {
        queryFormplayer: function (params, route) {
            var user = FormplayerFrontend.getChannel().request('currentUser'),
                lastRecordedLocation = FormplayerFrontend.getChannel().request('lastRecordedLocation'),
                timezoneOffsetMillis = (new Date()).getTimezoneOffset() * 60 * 1000 * -1,
                tzFromBrowser = Intl.DateTimeFormat().resolvedOptions().timeZone,
                formplayerUrl = user.formplayer_url,
                displayOptions = user.displayOptions || {},
                defer = $.Deferred(),
                options,
                menus;

            $.when(FormplayerFrontend.getChannel().request("appselect:apps")).done(function (appCollection) {
                if (!params.preview) {
                    // Make sure the user has access to the app
                    if (!appCollection.find(function (app) {
                        if (app.id && app.id === params.appId) {
                            return true;
                        }
                        if (app.get('copy_of') && app.get('copy_of') === params.copyOf) {
                            return true;
                        }
                    })) {
                        FormplayerFrontend.trigger(
                            'showError',
                            gettext('The application could not be found')
                        );
                        FormplayerFrontend.trigger('navigateHome');
                        defer.reject();
                        return;
                    }
                }

                options = {
                    success: function (parsedMenus, response) {
                        if (response.status === 'retry') {
                            FormplayerFrontend.trigger('retry', response, function () {
                                var newOptionsData = JSON.stringify($.extend(true, { mustRestore: true }, JSON.parse(options.data)));
                                menus.fetch($.extend(true, {}, options, { data: newOptionsData }));
                            }, gettext('Waiting for server progress'));
                        } else if (_.has(response, 'exception')) {
                            FormplayerFrontend.trigger('clearProgress');
                            if (params.clickedIcon && response.statusCode === 404) {
                                parsedMenus.removeCaseRow = true;
                                defer.resolve(parsedMenus);
                            } else {
                                FormplayerFrontend.trigger(
                                    'showError',
                                    response.exception,
                                    response.type === 'html'
                                );

                                var currentUrl = FormplayerFrontend.getCurrentRoute();
                                if (FormplayerFrontend.lastError === currentUrl) {
                                    FormplayerFrontend.lastError = null;
                                    FormplayerFrontend.trigger('navigateHome');
                                } else {
                                    FormplayerFrontend.lastError = currentUrl;
                                    FormplayerFrontend.trigger('navigation:back');
                                }
                                defer.reject();
                            }
                        } else {
                            if (response.smartLinkRedirect) {
                                if (user.environment === constants.PREVIEW_APP_ENVIRONMENT) {
                                    FormplayerFrontend.trigger('showSuccess', gettext("You have selected a case in a different domain. App Preview does not support this feature.", 5000));
                                    FormplayerFrontend.trigger('navigateHome');
                                    return;
                                }

                                // Drop last selection to avoid redirect loop if user presses back in the future
                                var urlObject = formplayerUtils.currentUrlToObject();
                                urlObject.setSelections(_.initial(urlObject.selections || []));
                                formplayerUtils.setUrlToObject(urlObject, true);

                                console.log("Redirecting to " + response.smartLinkRedirect);
                                document.location = response.smartLinkRedirect;
                                return;
                            }

                            FormplayerFrontend.trigger('clearProgress');
                            defer.resolve(parsedMenus);
                            // Only configure menu debugger if we didn't get a form entry response
                            if (!(response.session_id)) {
                                FormplayerFrontend.trigger('configureDebugger');
                            }
                        }
                    },
                    error: function (_, response) {
                        if (response.status === 423) {
                            FormplayerFrontend.trigger(
                                'showError',
                                errors.LOCK_TIMEOUT_ERROR
                            );
                        } else if (response.status === 401) {
                            FormplayerFrontend.trigger(
                                'showError',
                                formEntryUtils.reloginErrorHtml(),
                                true
                            );
                        } else {
                            FormplayerFrontend.trigger(
                                'showError',
                                gettext('Unable to connect to form playing service. ' +
                                        'Please report an issue if you continue to see this message.')
                            );
                        }
                        var urlObject = formplayerUtils.currentUrlToObject();
                        if (urlObject.selections) {
                            urlObject.selections.pop();
                            formplayerUtils.setUrlToObject(urlObject);
                        }
                        defer.reject();
                    },
                };
                var casesPerPage = parseInt($.cookie("cases-per-page-limit"))
                    || (window.innerWidth <= constants.SMALL_SCREEN_WIDTH_PX ? 5 : 10);
                const data = {
                    "username": user.username,
                    "restoreAs": user.restoreAs,
                    "domain": user.domain,
                    "app_id": params.appId,
                    "endpoint_id": params.endpointId,
                    "endpoint_args": params.endpointArgs,
                    "locale": displayOptions.language,
                    "selections": params.selections,
                    "offset": params.page * casesPerPage,
                    "search_text": params.search,
                    "form_session_id": params.sessionId,
                    "query_data": params.queryData,
                    "cases_per_page": casesPerPage,
                    "oneQuestionPerScreen": displayOptions.oneQuestionPerScreen,
                    "isPersistent": params.isPersistent,
                    "sortIndex": params.sortIndex,
                    "preview": params.preview,
                    "geo_location": lastRecordedLocation,
                    "tz_offset_millis": timezoneOffsetMillis,
                    "tz_from_browser": tzFromBrowser,
                    "selected_values": params.selectedValues,
                    "isShortDetail": params.isShortDetail,
                    "isRefreshCaseSearch": params.isRefreshCaseSearch,
                };
                options.data = JSON.stringify(data);
                options.url = formplayerUrl + '/' + route;

                menus = Collections();

                if (Object.freeze) {
                    Object.freeze(options);
                }
                const sentryData = _.pick(data, ["selections", "query_data", "app_id"]);
                Sentry.addBreadcrumb({
                    category: "formplayer",
                    message: "[request] " + route,
                    data: _.pick(sentryData, _.identity),
                });

                var callStartTime = performance.now();
                menus.fetch($.extend(true, {}, options)).always(function () {
                    if (data.query_data && data.query_data.results && data.query_data.results.initiatedBy === constants.queryInitiatedBy.DYNAMIC_SEARCH) {
                        var callEndTime = performance.now();
                        var callResponseTime = callEndTime - callStartTime;
                        $.ajax(initialPageData.reverse('api_histogram_metrics'), {
                            method: 'POST',
                            data: {responseTime: callResponseTime, metrics: "commcare.dynamic_search.response_time"},
                            error: function () {
                                console.log("API call failed to record metrics");
                            },
                        });
                    }
                });
            });

            return defer.promise();
        },
    };

    FormplayerFrontend.getChannel().reply("app:select:menus", function (options) {
        if (sessionStorage.selectedValues !== undefined) {
            const currentSelectedValues = JSON.parse(sessionStorage.selectedValues)[sessionStorage.queryKey];
            options.selectedValues = currentSelectedValues !== undefined && currentSelectedValues !== '' ? currentSelectedValues.split(',') : undefined;
        }
        if (!options.endpointId) {
            return API.queryFormplayer(options, options.isInitial ? "navigate_menu_start" : "navigate_menu");
        }

        var progressView = ProgressBar({
            progressMessage: gettext("Loading..."),
        });
        FormplayerFrontend.regions.getRegion('loadingProgress').show(progressView);

        var user = FormplayerFrontend.getChannel().request('currentUser');
        if (options.forceLoginAs && !user.restoreAs) {
            // Workflow requires a mobile user, likely because we're trying to access
            // a session endpoint as a web user. If user isn't logged in as, send them
            // to Log In As and save the current request options for when that's done.
            FormplayerFrontend.trigger("setLoginAsNextOptions", options);
            FormplayerFrontend.trigger("restore_as:list");

            // Caller expects a menu response, return a fake one
            return {abort: true};
        }

        // If an endpoint is provided, first claim any cases it references, then navigate
        return API.queryFormplayer(options, "get_endpoint");
    });

    FormplayerFrontend.getChannel().reply("icon:click", function (options) {
        return API.queryFormplayer(options, "get_endpoint");
    });

    FormplayerFrontend.getChannel().reply("entity:get:details", function (options, isPersistent, isShortDetail, isRefreshCaseSearch) {
        options.isPersistent = isPersistent;
        options.preview = FormplayerFrontend.currentUser.displayOptions.singleAppMode;
        options.isShortDetail = isShortDetail;
        options.isRefreshCaseSearch = isRefreshCaseSearch;
        return API.queryFormplayer(options, 'get_details');
    });

    return API;
});

