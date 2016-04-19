FormplayerFrontend.module("Entities", function(Entities, FormplayerFrontend, Backbone, Marionette, $, _){
   Entities.AppSelect = Backbone.Model.extend({
       urlRoot: "appSelects"
   });

    Entities.AppSelectCollection = Backbone.Collection.extend({
        url: "appSelects",
        model: AppSelect
    })
});