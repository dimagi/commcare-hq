'use strict';
hqDefine("cloudcare/js/formplayer/sessions/models", [
    'backbone',
    'cloudcare/js/formplayer/utils/utils',
], function (
    Backbone,
    utils
) {
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
