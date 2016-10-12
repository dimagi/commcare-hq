/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.SessionList", function (SessionList, FormplayerFrontend, Backbone, Marionette) {
    SessionList.SessionView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
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
        }
    });

    SessionList.SessionListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#session-view-list-template",
        childView: SessionList.SessionView,
        childViewContainer: "tbody",
    });
});
