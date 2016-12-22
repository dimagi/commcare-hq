/*global FormplayerFrontend */

FormplayerFrontend.module("Apps.Collections", function (Collections, FormplayerFrontend, Backbone) {
    Collections.App = Backbone.Collection.extend({
        url: "appSelects",
        model: FormplayerFrontend.Apps.Models.App,
    });
});

