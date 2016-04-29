FormplayerFrontend.module("AppSelect.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette, $, _) {
    AppList.AppSelect = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#app-select-list-item",

        events: {
            "click": "rowClick"
        },

        rowClick: function(e){
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.model.attributes._id);
        }
    });

    AppList.AppSelectView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#app-select-list",
        childView: AppList.AppSelect,
        childViewContainer: "tbody"
    });
});