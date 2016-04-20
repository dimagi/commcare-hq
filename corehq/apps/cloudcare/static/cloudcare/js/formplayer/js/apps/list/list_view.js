FormplayerFrontend.module("AppSelect.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette, $, _) {
    AppList.AppSelect = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#app-select-list-item",

        events: {
            "click": "rowClick"
        },

        rowClick: function(e){
            e.preventDefault();
            console.log("Model: " + this.model);
            var profileRef = "commcarehq.org/a/" + this.model.attributes.domain +
                    "/apps/download/" + this.model.attributes._id+ "/profile.ccpr";
            console.log("Profile Ref: " + profileRef);
            FormplayerFrontend.trigger("app:select", this.model);
        }
    });

    AppList.AppSelectView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover",
        template: "#app-select-list",
        childView: AppList.AppSelect,
        childViewContainer: "tbody"
    });
});