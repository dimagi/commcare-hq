
import Backbone from "backbone";
import Models from "cloudcare/js/formplayer/apps/models";

var self = Backbone.Collection.extend({
    url: "appSelects",
    model: Models,
});

export default function (apps) {
    return new self(apps);
};
