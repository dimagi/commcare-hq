'use strict';
hqDefine("cloudcare/js/formplayer/users/collections", [
    'backbone',
    'cloudcare/js/formplayer/users/models',
], function (
    Backbone,
    Models
) {
    /**
     * This collection represents a mobile worker user
     */
    var self = Backbone.Collection.extend({
        url: function () {
            if (!this.domain) {
                throw new Error('Cannot instantiate collection without domain');
            }
            return '/a/' + this.domain + '/cloudcare/api/login_as/users/';
        },
        model: Models.User,

        initialize: function (models, options) {
            options = options || {};
            this.domain = options.domain;
        },

        parse: function (responseObject) {
            this.total = responseObject.response.total;
            return responseObject.response.itemList;
        },

        sync: function (method, model, options) {
            options.xhrFields = {withCredentials: true};
            options.contentType = "application/json";
            return Backbone.Collection.prototype.sync.call(this, 'read', model, options);
        },
    });

    return function (users, options) {
        return new self(users, options);
    };
});
