'use strict';
/*global Backbone */

hqDefine("cloudcare/js/formplayer/apps/models", function () {
    return Backbone.Model.extend({
        urlRoot: "appSelects",
        idAttribute: "_id",
    });
});

