/*global FormplayerFrontend */

FormplayerFrontend.module("Users.Collections", function (Collections, FormplayerFrontend, Backbone) {
    /**
     * This collection represents a mobile worker user
     */
    Collections.User = Backbone.Collection.extend({
        url: function () {
            if (!this.domain) {
                throw new Error('Cannot instantiate collection without domain');
            }
            return '/a/' + this.domain + '/cloudcare/api/login_as/users/';
        },
        model: FormplayerFrontend.Users.Models.User,

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
});
