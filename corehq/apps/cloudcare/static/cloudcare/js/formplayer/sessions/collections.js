import Backbone from "backbone";
import Models from "cloudcare/js/formplayer/sessions/models";
import utils from "cloudcare/js/formplayer/utils/utils";

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

export default function (options) {
    return new session(options);
}
