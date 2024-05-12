'use strict';
hqDefine("cloudcare/js/formplayer/sessions/collections", [
    'backbone',
    'cloudcare/js/formplayer/sessions/models',
    'cloudcare/js/formplayer/utils/utils',
], function (
    Backbone,
    Models,
    utils
) {
    var session = Backbone.Collection.extend({
        model: Models,

        parse: function (response) {
            this.totalSessions = response.total_records;
            return response.sessions;
        },

        fetch: function (options) {
            utils.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.fetch.call(this, options);
        },
    });

    return function (options) {
        return new session(options);
    };
});
