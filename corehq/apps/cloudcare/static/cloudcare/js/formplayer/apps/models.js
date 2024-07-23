'use strict';
hqDefine("cloudcare/js/formplayer/apps/models", [
    'backbone',
], function (
    Backbone
) {
    return Backbone.Model.extend({
        urlRoot: "appSelects",
        idAttribute: "_id",
    });
});

