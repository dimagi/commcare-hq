/*global Backbone */

hqDefine("cloudcare/js/formplayer/menus/collections", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Util = hqImport("cloudcare/js/formplayer/utils/util");

    var MenuSelect = Backbone.Collection.extend({
        commonProperties: [
            'title',
            'type',
            'clearSession',
            'notification',
            'breadcrumbs',
            'appVersion',
            'appId',
            'persistentCaseTile',
            'tiles',
            'selections',
        ],

        entityProperties: [
            'actions',
            'styles',
            'headers',
            'currentPage',
            'pageCount',
            'titles',
            'numEntitiesPerRow',
            'maxWidth',
            'maxHeight',
            'widthHints',
            'useUniformUnits',
            'hasInlineTile',
            'sortIndices',
            'shouldWatchLocation',
            'shouldRequestLocation',
        ],

        commandProperties: [
            'layoutStyle',
        ],

        detailProperties: [
            'isPersistentDetail',
        ],

        formProperties: [
            'langs',
        ],

        parse: function (response) {
            _.extend(this, _.pick(response, this.commonProperties));

            if (response.selections) {
                var urlObject = Util.currentUrlToObject();
                urlObject.setSteps(response.selections);
                Util.setUrlToObject(urlObject);
            }

            if (response.commands) {
                _.extend(this, _.pick(response, this.commandProperties));
                return response.commands;
            } else if (response.entities) {
                _.extend(this, _.pick(response, this.entityProperties));
                return response.entities;
            } else if (response.type === "query") {
                return response.displays;
            } else if (response.details) {
                _.extend(this, _.pick(response, this.detailProperties));
                return response.details;
            } else if (response.tree) {
                // form entry time, doggy
                _.extend(this, _.pick(response, this.formProperties));
                FormplayerFrontend.trigger('startForm', response, this.app_id);
            }
        },

        sync: function (method, model, options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });

    return function (response, options) {
        return new MenuSelect(response, options);
    };
});

