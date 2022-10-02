/*global Backbone */

hqDefine("cloudcare/js/formplayer/sessions/models", function () {
    var Utils = hqImport("cloudcare/js/formplayer/utils/utils");

    return Backbone.Model.extend({
        isNew: function () {
            return !this.get('sessionId');
        },
        sync: function (method, model, options) {
            Utils.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
        },
    });
});
