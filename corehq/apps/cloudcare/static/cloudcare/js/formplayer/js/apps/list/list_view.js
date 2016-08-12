/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.AppList", function (AppList, FormplayerFrontend, Backbone, Marionette) {
    AppList.GridItem = Marionette.ItemView.extend({
        template: "#row-template",
        tagName: "div",
        className: "grid-item col-sm-4 text-center formplayer-request",
        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("app:select", this.model.get('_id'));
        },
    });

    AppList.GridView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#grid-template",
        childView: AppList.GridItem,
        childViewContainer: ".application-container",

        events: {
            'click #incompleteSessionsItem': 'incompleteSessionsClick',
            'click #syncItem': 'syncClick',
        },
        incompleteSessionsClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("sessions");
        },
        syncClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("sync");
        },
    });
})
;