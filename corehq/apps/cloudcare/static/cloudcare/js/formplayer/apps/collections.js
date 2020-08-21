/*global Backbone, FormplayerFrontend */

hqDefine("cloudcare/js/formplayer/apps/collections", function() {
    var self = Backbone.Collection.extend({
        url: "appSelects",
        model: FormplayerFrontend.Apps.Models.App,
    });

    return function (apps) {
        return new self(apps);
    };
});
