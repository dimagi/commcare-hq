/*global Util, Backbone */

hqDefine("cloudcare/js/formplayer/sessions/collections", function () {

    var session = Backbone.Collection.extend({
        model: hqImport("cloudcare/js/formplayer/sessions/models"),

        parse: function (response) {
            return response.sessions;
        },

        fetch: function (options) {
            Util.setCrossDomainAjaxOptions(options);
            return Backbone.Collection.prototype.fetch.call(this, options);
        },
    });

    return function (options) {
        return new session(options);
    };
});
