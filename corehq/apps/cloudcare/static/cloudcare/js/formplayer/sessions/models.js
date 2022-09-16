/*global Backbone */

hqDefine("cloudcare/js/formplayer/sessions/models", function () {
    return Backbone.Model.extend({
        isNew: function () {
            return !this.get('sessionId');
        },
        sync: function (method, model, options) {
            hqImport("cloudcare/js/formplayer/utils/utils").setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });
});
