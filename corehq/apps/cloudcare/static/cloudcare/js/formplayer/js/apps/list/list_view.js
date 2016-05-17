/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette) {
    AppList.GridRow = Marionette.ItemView.extend({
        template: "#row-template",
        tagName: "td",

        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.model.attributes._id);
        },
    });

    AppList.GridView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#grid-template",
        childView: AppList.GridRow,
        attachHtml: function (collectionView, itemView) {
            var index = this.collection.indexOf(itemView.model);
            // This is terrible, but not sure a better way to do this - for every 3 columns make a new row.
            if (index === 0) {
                collectionView.$("tbody").append("<tr>");
            }
            if (index % 3 === 0) {
                collectionView.$("tbody").append("</tr><tr>");
            }
            collectionView.$("tbody").append(itemView.el);
            if (index === this.collection.length) {
                collectionView.$("tbody").append("</tr>");
            }
        },
    });
});