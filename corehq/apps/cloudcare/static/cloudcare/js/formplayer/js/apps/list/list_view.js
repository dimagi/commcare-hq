/*global FormplayerFrontend */

FormplayerFrontend.module("AppSelect.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette) {
    AppList.AppSelect = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#app-select-list-item",

        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.model.attributes._id);
        },
    });

    AppList.AppSelectView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#app-select-list",
        childView: AppList.AppSelect,
        childViewContainer: "tbody",
    });

    // A Grid Row
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

    // The grid view
    AppList.GridView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#grid-template",
        childView: AppList.GridRow,
        //childViewContainer: "tbody",
        attachHtml: function (collectionView, itemView) {
            var index = this.collection.indexOf(itemView.model);
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