/*global FormplayerFrontend */

FormplayerFrontend.module("Users.Models", function(Models, FormplayerFrontend, Backbone) {
    Models.User = Backbone.Model.extend();
    Models.CurrentUser = Backbone.Model.extend({});
});
