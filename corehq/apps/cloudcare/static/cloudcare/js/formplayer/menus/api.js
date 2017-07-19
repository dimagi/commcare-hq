/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

FormplayerFrontend.module("Menus", function (Menus, FormplayerFrontend, Backbone, Marionette, $) {

    Menus.API = {

        queryFormplayer: function (params, route) {

            var user = FormplayerFrontend.request('currentUser'),
                formplayerUrl = user.formplayer_url,
                displayOptions = user.displayOptions || {},
                defer = $.Deferred(),
                options,
                menus;
            options = {
                success: function (parsedMenus, response) {
                    if (response.status === 'retry') {
                        FormplayerFrontend.trigger('retry', response, function() {
                            var newOptionsData = JSON.stringify($.extend(true, { mustRestore: true }, JSON.parse(options.data)));
                            menus.fetch($.extend(true, {}, options, { data: newOptionsData }));
                        }, gettext('Waiting for server progress'));
                    } else if (response.hasOwnProperty('exception')){
                        FormplayerFrontend.trigger(
                            'showError',
                            response.exception || FormplayerFrontend.Constants.GENERIC_ERROR,
                            response.type === 'html'
                        );
                        FormplayerFrontend.trigger('navigation:back');
                    } else {
                        FormplayerFrontend.trigger('clearProgress');
                        defer.resolve(parsedMenus);
                        if (response.menuSessionId) {
                            FormplayerFrontend.trigger('configureDebugger', response.menuSessionId);
                        }
                    }
                },
                error: function () {
                    FormplayerFrontend.trigger(
                        'showError',
                        gettext('Unable to connect to form playing service. ' +
                                'Please report an issue if you continue to see this message.')
                    );
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
                "previewCommand": params.previewCommand,
                "installReference": params.installReference,
                "oneQuestionPerScreen": displayOptions.oneQuestionPerScreen,
                "isPersistent": params.isPersistent,
                "useLiveQuery": user.useLiveQuery,
            });
            options.url = formplayerUrl + '/' + route;

            menus = new FormplayerFrontend.Menus.Collections.MenuSelect();

            if (Object.freeze) {
                Object.freeze(options);
            }
            menus.fetch($.extend(true, {}, options));
            return defer.promise();
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (options) {
        return Menus.API.queryFormplayer(options, 'navigate_menu');
    });

    FormplayerFrontend.reqres.setHandler("entity:get:details", function (options, isPersistent) {
        options.isPersistent = isPersistent;
        return Menus.API.queryFormplayer(options, 'get_details');
    });
});

