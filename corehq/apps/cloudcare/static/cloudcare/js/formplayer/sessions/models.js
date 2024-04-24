'use strict';
/*global Backbone */

hqDefine("cloudcare/js/formplayer/sessions/models", function () {
    var utils = hqImport("cloudcare/js/formplayer/utils/utils");

    return Backbone.Model.extend({
        isNew: function () {
            return !this.get('sessionId');
        },
        sync: function (method, model, options) {
            utils.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });
});
