/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Menus.Collections", function (Collections, FormplayerFrontend, Backbone, Marionette, $) {

    Collections.MenuSelect = Backbone.Collection.extend({

        model: FormplayerFrontend.Menus.Models.MenuSelect,

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
        ],

        commandProperties: [
            'layoutStyle',
        ],

        parse: function (response, request) {
            _.extend(this, _.pick(response, this.commonProperties));

            if (response.commands) {
                _.extend(this, _.pick(response, this.commandProperties));
                return response.commands;
            } else if (response.entities) {
                _.extend(this, _.pick(response, this.entityProperties));
                return response.entities;
            } else if (response.type === "query") {
                return response.displays;
            } else if (response.details) {
                return response.details;
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
});

