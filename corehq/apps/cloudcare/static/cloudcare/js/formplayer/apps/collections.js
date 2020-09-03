/*global Backbone */

hqDefine("cloudcare/js/formplayer/apps/collections", function() {
    var self = Backbone.Collection.extend({
        url: "appSelects",
        model: hqImport("cloudcare/js/formplayer/apps/models"),
    });

    return function (apps) {
        return new self(apps);
    };
});
