/*global FormplayerFrontend */

FormplayerFrontend.module("Users.Collections", function(Collections, FormplayerFrontend, Backbone) {
    /**
     * This collection represents a mobile worker user
     */
    Collections.User = Backbone.Collection.extend({
        url: function() {
            if (!this.domain) {
                throw new Error('Cannot instantiate collection without domain');
            }
            return '/a/' + this.domain + '/settings/users/commcare/';
        },
        model: FormplayerFrontend.Users.Models.User,

        initialize: function(models, options) {
            options = options || {};
            this.domain = options.domain;
        },

        parse: function(responseObject) {
            this.total = responseObject.response.total;
            return responseObject.response.itemList;
        },

        sync: function (method, model, options) {
            options.xhrFields = {withCredentials: true};
            // Need to set these headers to allow access to @allow_remote_invocation
            options.beforeSend = function(xhr) {
                xhr.setRequestHeader('DjNg-Remote-Method', 'get_pagination_data');
                xhr.setRequestHeader("X-CSRFToken", $("#csrfTokenContainer").val());
            };
            options.contentType = "application/json";
            options.data = options.data || JSON.stringify({});
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });
});
