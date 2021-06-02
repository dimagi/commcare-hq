/*global Marionette, moment */

hqDefine("cloudcare/js/formplayer/sessions/views", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");

    var SessionView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
            "keydown .module-heading": "activateKeyAction",
            "click .module-delete-control": "onDeleteSession",
            "keydown .module-delete-control": "deleteKeyAction",
        },

        template: _.template($("#session-view-item-template").html() || ""),

        rowClick: function (e) {
            e.preventDefault();
            var model = this.model;
            FormplayerFrontend.trigger("getSession", model.get('sessionId'));
        },

        activateKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.rowClick(e);
            }
        },

        templateContext: function () {
            return {
                humanDateOpened: moment(this.model.get('dateOpened')).fromNow(),
                labelId: "SessionLabel-".concat(this.model.get('sessionId')),
            };
        },
        onDeleteSession: function (e) {
            var self = this;
            e.preventDefault();
            e.stopPropagation();
            hqImport("cloudcare/js/formplayer/utils/util").confirmationModal({
                title: gettext('Delete incomplete form?'),
                message: gettext("Are you sure you want to delete '" + self.model.get('title') + "'"),
                confirmText: gettext('Yes'),
                cancelText: gettext('No'),
                onConfirm: function () {
                    FormplayerFrontend.getChannel().request("deleteSession", self.model);
                },
            });
        },
        deleteKeyAction: function (e) {
            // The ARIA button role would activate on either Space or Enter,
            // but we require Enter for now to avoid accidental deletions.
            if (e.keyCode === 13) {
                this.onDeleteSession(e);
            }
        },
    });

    var SessionListView = Marionette.CollectionView.extend({
        tagName: "div",
        childView: SessionView,
        childViewContainer: "tbody",
        getTemplate: function () {
            var user = FormplayerFrontend.getChannel().request('currentUser');
            var id = "#session-view-list-web-apps-template";
            if (user.environment === hqImport("cloudcare/js/formplayer/constants").PREVIEW_APP_ENVIRONMENT) {
                id = "#session-view-list-preview-template";
            }
            return _.template($(id).html() || "");
        },
    });

    return function (options) {
        return new SessionListView(options);
    };
});
