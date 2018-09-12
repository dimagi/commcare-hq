/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Sessions.Models", function (Models, FormplayerFrontend, Backbone, Marionette, $) {

    Models.FormEntrySession = Backbone.Model.extend({
        isNew: function () {
            return !this.get('sessionId');
        },
        sync: function (method, model, options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });
});
