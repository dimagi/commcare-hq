/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Sessions.Collections", function (Collections, FormplayerFrontend, Backbone, Marionette, $) {

    Collections.FormEntrySession = Backbone.Collection.extend({

        model: FormplayerFrontend.Sessions.Models.FormEntrySession,

        parse: function (response) {
            return response.sessions;
        },

        fetch: function (options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.fetch.call(this, options);
        },
    });

});
