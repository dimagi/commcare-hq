'use strict';
/*global Backbone */

hqDefine("cloudcare/js/formplayer/apps/collections", function () {
    var Models = hqImport("cloudcare/js/formplayer/apps/models");

    var self = Backbone.Collection.extend({
        url: "appSelects",
        model: Models,
    });

    return function (apps) {
        return new self(apps);
    };
});
