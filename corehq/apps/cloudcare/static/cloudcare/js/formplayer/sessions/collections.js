/*global Backbone */

hqDefine("cloudcare/js/formplayer/sessions/collections", function () {

    var session = Backbone.Collection.extend({
        model: hqImport("cloudcare/js/formplayer/sessions/models"),

        parse: function (response) {
            this.totalSessions = response.total_records;
            return response.sessions;
        },

        fetch: function (options) {
            hqImport("cloudcare/js/formplayer/utils/util").setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.fetch.call(this, options);
        },
    });

    return function (options) {
        return new session(options);
    };
});
