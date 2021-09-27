/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

hqDefine("cloudcare/js/formplayer/menus/api", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Util = hqImport("cloudcare/js/formplayer/utils/util");

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
                        return app.id === params.appId || app.get('copy_of') === params.copyOf;
                    })) {
                        FormplayerFrontend.trigger(
                            'showError',
                            gettext('Permission Denied')
                        );
                        FormplayerFrontend.trigger('navigateHome');
                        defer.reject();
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
                            FormplayerFrontend.trigger(
                                'showError',
                                response.exception || hqImport("cloudcare/js/formplayer/constants").GENERIC_ERROR,
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

                        } else {
                            if (response.smartLinkRedirect) {
                                // TODO: this is really slow
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
                                hqImport("cloudcare/js/form_entry/errors").LOCK_TIMEOUT_ERROR
                            );
                        } else if (response.status === 401) {
                            FormplayerFrontend.trigger(
                                'showError',
                                hqImport("cloudcare/js/form_entry/utils").reloginErrorHtml(),
                                true
                            );
                        } else {
                            FormplayerFrontend.trigger(
                                'showError',
                                gettext('Unable to connect to form playing service. ' +
                                        'Please report an issue if you continue to see this message.')
                            );
                        }
                        var urlObject = Util.currentUrlToObject();
                        if (urlObject.selections) {
                            urlObject.selections.pop();
                            Util.setUrlToObject(urlObject);
                        }
                        defer.reject();
                    },
                };
                var casesPerPage = parseInt($.cookie("cases-per-page-limit")) || 10;
                options.data = JSON.stringify({
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
                    "menu_session_id": params.sessionId,
                    "force_manual_action": params.forceManualAction,
                    "query_data": params.queryData,
                    "cases_per_page": casesPerPage,
                    "smart_link_template": params.smartLinkTemplate,
                    "oneQuestionPerScreen": displayOptions.oneQuestionPerScreen,
                    "isPersistent": params.isPersistent,
                    "useLiveQuery": user.useLiveQuery,
                    "sortIndex": params.sortIndex,
                    "preview": params.preview,
                    "geo_location": lastRecordedLocation,
                    "tz_offset_millis": timezoneOffsetMillis,
                    "tz_from_browser": tzFromBrowser,
                });
                options.url = formplayerUrl + '/' + route;

                menus = hqImport("cloudcare/js/formplayer/menus/collections")();

                if (Object.freeze) {
                    Object.freeze(options);
                }
                menus.fetch($.extend(true, {}, options));
            });

            return defer.promise();
        },
    };

    FormplayerFrontend.getChannel().reply("app:select:menus", function (options) {
        if (!options.endpointId) {
            return API.queryFormplayer(options, options.isInitial ? "navigate_menu_start" : "navigate_menu");
        }

        var user = FormplayerFrontend.getChannel().request('currentUser');
        if (options.forceLoginAs && !user.restoreAs) {
            // Workflow requires a mobile user, likely because we're trying to access
            // a session endpoint as a web user. If user isn't logged in as, send them
            // to Login As and save the current request options for when that's done.
            FormplayerFrontend.trigger("setLoginAsNextOptions", options);
            FormplayerFrontend.trigger("restore_as:list");

            // Caller expects a menu response, return a fake one
            return {abort: true};
        }

        // If an endpoint is provided, first claim any cases it references, then navigate
        return API.queryFormplayer(options, "get_endpoint");
    });

    FormplayerFrontend.getChannel().reply("entity:get:details", function (options, isPersistent) {
        options.isPersistent = isPersistent;
        options.preview = FormplayerFrontend.currentUser.displayOptions.singleAppMode;
        return API.queryFormplayer(options, 'get_details');
    });

    return 1;
});

