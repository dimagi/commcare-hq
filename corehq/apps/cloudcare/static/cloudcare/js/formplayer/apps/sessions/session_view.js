/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.SessionList", function (SessionList, FormplayerFrontend, Backbone, Marionette) {
    SessionList.SessionView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
            "click .module-delete-control": "onDeleteSession"
        },

        template: "#session-view-item-template",

        rowClick: function (e) {
            e.preventDefault();
            var model = this.model;
            FormplayerFrontend.trigger("getSession", model.get('sessionId'));
        },

        templateHelpers: function(e) {
            return {
                humanDateOpened: moment(this.model.get('dateOpened')).fromNow(),
            };
        },
        onDeleteSession: function(e) {
            e.preventDefault();
            e.stopPropagation();
            var result = FormplayerFrontend.request("deleteSession", this.model);
        },
    });

    SessionList.SessionListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#session-view-list-template",
        childView: SessionList.SessionView,
        childViewContainer: "tbody",
    });
});
