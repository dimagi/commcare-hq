/*global FormplayerFrontend, Formplayer */

/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

hqDefine("cloudcare/js/formplayer/menus/api", function () {
    var API = {
        queryFormplayer: function (params, route) {
            var user = FormplayerFrontend.getChannel().request('currentUser'),
                lastRecordedLocation = FormplayerFrontend.getChannel().request('lastRecordedLocation'),
                timezoneOffsetMillis = (new Date()).getTimezoneOffset() * 60 * 1000 * -1,
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
                        } else if (response.hasOwnProperty('exception')) {
                            FormplayerFrontend.trigger('clearProgress');
                            FormplayerFrontend.trigger(
                                'showError',
                                response.exception || FormplayerFrontend.Constants.GENERIC_ERROR,
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

                        } else {
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
                                Formplayer.Errors.LOCK_TIMEOUT_ERROR
                            );
                        } else if (response.status === 401) {
                            FormplayerFrontend.trigger(
                                'showError',
                                Formplayer.Utils.reloginErrorHtml(),
                                true
                            );
                        } else {
                            FormplayerFrontend.trigger(
                                'showError',
                                gettext('Unable to connect to form playing service. ' +
                                        'Please report an issue if you continue to see this message.')
                            );
                        }
                        defer.reject();
                    },
                };
                options.data = JSON.stringify({
                    "username": user.username,
                    "restoreAs": user.restoreAs,
                    "domain": user.domain,
                    "app_id": params.appId,
                    "locale": displayOptions.language,
                    "selections": params.steps,
                    "offset": params.page * 10,
                    "search_text": params.search,
                    "menu_session_id": params.sessionId,
                    "query_dictionary": params.queryDict,
                    "installReference": params.installReference,
                    "oneQuestionPerScreen": displayOptions.oneQuestionPerScreen,
                    "isPersistent": params.isPersistent,
                    "useLiveQuery": user.useLiveQuery,
                    "sortIndex": params.sortIndex,
                    "preview": params.preview,
                    "geo_location": lastRecordedLocation,
                    "tz_offset_millis": timezoneOffsetMillis,
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
        var isInitial = options.isInitial;
        return API.queryFormplayer(options, isInitial ? 'navigate_menu_start' : 'navigate_menu');
    });

    FormplayerFrontend.getChannel().reply("entity:get:details", function (options, isPersistent) {
        options.isPersistent = isPersistent;
        options.preview = FormplayerFrontend.currentUser.displayOptions.singleAppMode;
        return API.queryFormplayer(options, 'get_details');
    });

    return 1;
});

