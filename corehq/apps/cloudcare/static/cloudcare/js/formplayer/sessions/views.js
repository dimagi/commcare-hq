/*global FormplayerFrontend, moment, Util */

hqDefine("cloudcare/js/formplayer/sessions/views", function () {
    var SessionView = Marionette.View.extend({
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

        templateContext: function (e) {
            return {
                humanDateOpened: moment(this.model.get('dateOpened')).fromNow(),
            };
        },
        onDeleteSession: function (e) {
            var self = this;
            e.preventDefault();
            e.stopPropagation();
            Util.confirmationModal({
                title: gettext('Delete incomplete form?'),
                message: gettext("Are you sure you want to delete '" + self.model.get('title') + "'"),
                confirmText: gettext('Yes'),
                cancelText: gettext('No'),
                onConfirm: function () {
                    FormplayerFrontend.getChannel().request("deleteSession", self.model);
                },
            });
        },
    });

    var SessionTableView = Marionette.CollectionView.extend({
        childView: SessionView,
        tagName: "tbody",
    });

    var SessionListView = Marionette.View.extend({
        tagName: "div",
        regions: {
            body: {
                el: 'table',
            },
        },
        onRender: function () {
            this.showChildView('body', new SessionTableView({
                collection: this.collection,
            }));
        },
        getTemplate: function () {
            var user = FormplayerFrontend.getChannel().request('currentUser');
            if (user.environment === FormplayerFrontend.Constants.PREVIEW_APP_ENVIRONMENT) {
                return "#session-view-list-preview-template";
            }
            return "#session-view-list-web-apps-template";
        },
    });

    return function (options) {
        return new SessionListView(options);
    };
});
