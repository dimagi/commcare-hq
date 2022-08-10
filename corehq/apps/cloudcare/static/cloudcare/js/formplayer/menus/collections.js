/*global Backbone */

hqDefine("cloudcare/js/formplayer/menus/collections", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Util = hqImport("cloudcare/js/formplayer/utils/util");

    var MenuSelect = Backbone.Collection.extend({
        commonProperties: [
            'appId',
            'appVersion',
            'breadcrumbs',
            'clearSession',
            'notification',
            'persistentCaseTile',
            'queryKey',
            'selections',
            'tiles',
            'title',
            'type',
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

            var urlObject = Util.currentUrlToObject(),
                updateUrl = false;
            if (!urlObject.appId && response.appId) {
                // will be undefined on urlObject when coming from an incomplete form
                urlObject.appId = response.appId;
                this.appId = urlObject.appId;
                updateUrl = true;
            }
            if (response.selections) {
                urlObject.setSelections(response.selections);
                sessionStorage.removeItem('selectedValues');
                updateUrl = true;
            }
            if (updateUrl) {
                Util.setUrlToObject(urlObject, true);
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
                FormplayerFrontend.trigger('startForm', response);
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

