'use strict';
hqDefine("cloudcare/js/formplayer/apps/collections", [
    'backbone',
    'cloudcare/js/formplayer/apps/models',
], function (
    Backbone,
    Models
) {
    var self = Backbone.Collection.extend({
        url: "appSelects",
        model: Models,
    });

    return function (apps) {
        return new self(apps);
    };
});
