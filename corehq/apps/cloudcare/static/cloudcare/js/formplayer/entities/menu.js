/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {


    var API = {

        getMenus: function (params) {

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
                            menus.fetch($.extend(true, {}, options));
                        }, gettext('Waiting for server progress'));
                    } else if (response.exception){
                        FormplayerFrontend.trigger(
                            'showError',
                            response.exception,
                            response.type === 'html'
                        );
                    } else {
                        FormplayerFrontend.trigger('clearProgress');
                        defer.resolve(parsedMenus);
                    }
                },
                error: function () {
                    FormplayerFrontend.request(
                        'showError',
                        gettext('Unable to connect to form playing service. ' +
                                'Please report an issue if you continue to see this message.')
                    );
                    defer.resolve();
                },
            };

            options.data = JSON.stringify({
                "username": user.username,
                "restoreAs": user.restoreAs,
                "domain": user.domain,
                "app_id": params.appId,
                "locale": user.language,
                "selections": params.steps,
                "offset": params.page * 10,
                "search_text": params.search,
                "menu_session_id": params.sessionId,
                "query_dictionary": params.queryDict,
                "previewCommand": params.previewCommand,
                "installReference": params.installReference,
                "oneQuestionPerScreen": ko.utils.unwrapObservable(displayOptions.oneQuestionPerScreen),
            });
            options.url = formplayerUrl + '/navigate_menu';

            menus = new FormplayerFrontend.Menus.Collections.MenuSelect();

            if (Object.freeze) {
                Object.freeze(options);
            }
            menus.fetch($.extend(true, {}, options));
            return defer.promise();
        },
    };

    FormplayerFrontend.reqres.setHandler("app:select:menus", function (options) {
        return API.getMenus(options);
    });
});
