/*global FormplayerFrontend */

FormplayerFrontend.module("Apps.Models", function (Models, FormplayerFrontend, Backbone) {
    Models.App = Backbone.Model.extend({
        urlRoot: "appSelects",
        idAttribute: "_id",
    });
});

