/*global FormplayerFrontend, Util */

/**
 * Backbone model for listing and selecting CommCare menus (modules, forms, and cases)
 */

FormplayerFrontend.module("Entities", function (Entities, FormplayerFrontend, Backbone, Marionette, $) {

    Entities.MenuSelect = Backbone.Model.extend({});

    Entities.MenuSelectCollection = Backbone.Collection.extend({

        model: Entities.MenuSelect,

        commonProperties: [
            'title',
            'type',
            'clearSession',
            'notification',
            'breadcrumbs',
            'appVersion',
            'appId',
            'persistentCaseTile',
        ],

        entityProperties: [
            'action',
            'styles',
            'headers',
            'currentPage',
            'pageCount',
            'titles',
            'numEntitiesPerRow',
            'maxWidth',
            'maxHeight',
        ],

        parse: function (response, request) {
            _.extend(this, _.pick(response, this.commonProperties));

            if (response.commands) {
                return response.commands;
            } else if (response.entities) {
                _.extend(this, _.pick(response, this.entityProperties));
                return response.entities;
            } else if (response.type === "query") {
                return response.displays;
            } else if (response.tree){
                // form entry time, doggy
                FormplayerFrontend.trigger('startForm', response, this.app_id);
            }
        },

        sync: function (method, model, options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });

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
                        }, gettext('Please wait while we sync your user...'));
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

            menus = new Entities.MenuSelectCollection();

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
