'use strict';
/**
 *  A menu is implemented as a collection of items. Typically, the user
 *  selects one of these items. The query screen is also implemented as
 *  a menu, where each search field is an item.
 */
hqDefine("cloudcare/js/formplayer/menus/collections", [
    'underscore',
    'backbone',
    'sentry_browser',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/utils/utils',
], function (
    _,
    Backbone,
    Sentry,
    FormplayerFrontend,
    Utils
) {
    function addBreadcrumb(collection, type, data) {
        Sentry.addBreadcrumb({
            category: "formplayer",
            message: "[response] " + type + ": " + collection.title + " (" + collection.queryKey + ")",
            data: data,
        });
    }

    var MenuSelect = Backbone.Collection.extend({
        commonProperties: [
            'appId',
            'appVersion',
            'breadcrumbs',
            'clearSession',
            'description',
            'notification',
            'persistentCaseTile',
            'queryKey',
            'selections',
            'tiles',
            'title',
            'type',
            'noItemsText',
            'dynamicSearch',
            'metaData',
        ],

        entityProperties: [
            'actions',
            'currentPage',
            'hasInlineTile',
            'headers',
            'maxHeight',
            'maxWidth',
            'numEntitiesPerRow',
            'pageCount',
            'redoLast',
            'shouldRequestLocation',
            'shouldWatchLocation',
            'sortIndices',
            'styles',
            'titles',
            'useUniformUnits',
            'widthHints',
            'multiSelect',
            'maxSelectValue',
            'hasDetails',
            'groupHeaderRows',
            'queryResponse',
            'endpointActions',
            'selectText',
        ],

        commandProperties: [
            'layoutStyle',
        ],

        detailProperties: [
            'isPersistentDetail',
        ],

        formProperties: [
            'langs',
            'session_id',
        ],

        queryProperties: [
            'groupHeaders',
            'searchOnClear',
        ],

        parse: function (response) {
            _.extend(this, _.pick(response, this.commonProperties));

            var urlObject = Utils.currentUrlToObject(),
                updateUrl = false;
            if (!urlObject.appId && response.appId) {
                // will be undefined on urlObject when coming from an incomplete form
                urlObject.appId = response.appId;
                this.appId = urlObject.appId;
                updateUrl = true;
            }
            if (response.selections) {
                urlObject.setSelections(response.selections);
                updateUrl = true;
            }
            if (updateUrl) {
                Utils.setUrlToObject(urlObject, true);
            }
            let sentryData = _.pick(
                _.pick(response, ["queryKey", "selections"]),
                _.identity
            );
            if (response.commands) {
                _.extend(this, _.pick(response, this.commandProperties));
                addBreadcrumb(this, "menu", _.extend(sentryData, {
                    'commands': _.pluck(response.commands, "displayText"),
                }));
                return response.commands;
            } else if (response.entities) {
                addBreadcrumb(this, "caseList", _.extend(sentryData, {
                    length: response.entities.length,
                    multiSelect: response.multiSelect,
                }));
                // backwards compatibility - remove after FP deploy of #1374
                _.defaults(response, {"hasDetails": true});
                _.extend(this, _.pick(response, this.entityProperties));
                return response.entities;
            } else if (response.type === "query") {
                addBreadcrumb(this, "query", sentryData);
                _.extend(this, _.pick(response, this.queryProperties));
                return response.displays;
            } else if (response.details) {
                addBreadcrumb(this, "details", sentryData);
                _.extend(this, _.pick(response, this.detailProperties));
                return response.details;
            } else if (response.tree) {
                // form entry time, doggy
                addBreadcrumb(this, "startForm", sentryData);
                _.extend(this, _.pick(response, this.formProperties));
                FormplayerFrontend.trigger('startForm', response);
            }
        },

        sync: function (method, model, options) {
            Utils.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });

    return function (response, options) {
        return new MenuSelect(response, options);
    };
});
