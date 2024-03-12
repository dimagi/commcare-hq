'use strict';
/*global Backbone */

hqDefine("cloudcare/js/formplayer/sessions/collections", function () {
    var Models = hqImport("cloudcare/js/formplayer/sessions/models"),
        utils = hqImport("cloudcare/js/formplayer/utils/utils");

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
