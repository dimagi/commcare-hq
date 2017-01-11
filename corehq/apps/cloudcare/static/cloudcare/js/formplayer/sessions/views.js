/*global FormplayerFrontend, moment, Util */

FormplayerFrontend.module("SessionNavigate.SessionList", function (SessionList, FormplayerFrontend, Backbone, Marionette) {
    SessionList.SessionView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
            "click .module-delete-control": "onDeleteSession",
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
            var self = this;
            e.preventDefault();
            e.stopPropagation();
            Util.confirmationModal({
                title: gettext('Delete incomplete form?'),
                message: gettext("Are you sure you want to delete '" + self.model.get('title') + "'"),
                confirmText: gettext('Yes'),
                cancelText: gettext('No'),
                onConfirm: function() {
                    FormplayerFrontend.request("deleteSession", self.model);
                },
            });
        },
    });

    SessionList.SessionListView = Marionette.CompositeView.extend({
        tagName: "div",
        getTemplate: function() {
            var user = FormplayerFrontend.request('currentUser');
            if (user.environment === FormplayerFrontend.Constants.PREVIEW_APP_ENVIRONMENT) {
                return "#session-view-list-preview-template";
            }
            return "#session-view-list-web-apps-template";
        },
        childView: SessionList.SessionView,
        childViewContainer: "tbody",
    });
});
