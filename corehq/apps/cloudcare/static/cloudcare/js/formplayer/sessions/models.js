import Backbone from "backbone";
import utils from "cloudcare/js/formplayer/utils/utils";

export default Backbone.Model.extend({
    isNew: function () {
        return !this.get('sessionId');
    },
    sync: function (method, model, options) {
        utils.setCrossDomainAjaxOptions(options);
        return Backbone.Collection.prototype.sync.call(this, 'create', model, options);
    },
});
