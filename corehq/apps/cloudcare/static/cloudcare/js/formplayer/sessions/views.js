/*global _, moment, Util */

hqDefine("cloudcare/js/formplayer/sessions/views", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");

    var SessionView = Marionette.View.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
            "click .module-delete-control": "onDeleteSession",
        },

        template: _.template($("#session-view-item-template").html() || ""),

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
