/*global Backbone, Marionette, moment */

hqDefine("cloudcare/js/formplayer/sessions/views", function () {
    var constants = hqImport("cloudcare/js/formplayer/constants"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        FormplayerUtils = hqImport("cloudcare/js/formplayer/utils/utils"),
        utils = hqImport("cloudcare/js/formplayer/utils/utils");

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
            utils.confirmationModal({
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
        template: _.template($("#session-view-list-template").html() || ""),

        initialize: function (options) {
            this.model = new Backbone.Model({
                page: options.pageNumber + 1 || 1,
                limit: options.pageSize,
            });
            this.model.on('change', function () {
                this.options.listSessions(this.model.get('page') - 1, this.model.get("limit"));
                this.render.bind(this);
            }.bind(this));
        },
        events: {
            'click @ui.paginators': 'onClickPageNumber',
            'keypress @ui.paginators': 'paginateKeyAction',
            'click @ui.paginationGoButton': 'paginationGoAction',
            'keypress @ui.paginationGoTextBox': 'paginationGoKeyAction',
            'change @ui.sessionsPerPageLimit': 'onPerPageLimitChange',
        },
        ui: {
            paginators: '.js-page',
            paginationGoButton: '#pagination-go-button',
            paginationGoTextBox: '.module-go-container',
            paginationGoText: '#goText',
            sessionsPerPageLimit: '.per-page-limit',
        },
        onClickPageNumber: function (e) {
            e.preventDefault();
            var page = $(e.currentTarget).data("id");
            this.model.set('page', page + 1);
        },
        onPerPageLimitChange: function (e) {
            e.preventDefault();
            var sessionsPerPage = this.ui.sessionsPerPageLimit.val();
            this.model.set("limit", Number(sessionsPerPage));
            this.model.set("page", 1);
            FormplayerUtils.savePerPageLimitCookie("sessions", this.model.get("limit"));
        },
        paginationGoAction: function (e) {
            e.preventDefault();
            var goText = Number(this.ui.paginationGoText.val());
            var pageNo = utils.paginationGoPageNumber(goText, this.options.totalPages);
            this.model.set('page', pageNo);
        },
        paginateKeyAction: function (e) {
            // Pressing Enter on a pagination control activates it.
            if (e.which === 13 || e.keyCode === 13) {
                e.stopImmediatePropagation();
                this.onClickPageNumber(e);
            }
        },
        paginationGoKeyAction: function (e) {
            // Pressing Enter in the go box activates it.
            if (e.which === 13 || e.keyCode === 13) {
                e.stopImmediatePropagation();
                this.paginationGoAction(e);
            }
        },
        templateContext: function () {
            var user = FormplayerFrontend.getChannel().request('currentUser');
            var paginationConfig = utils.paginateOptions(this.options.pageNumber, this.options.totalPages);
            return {
                total: this.collection.totalSessions,
                totalPages: this.options.totalPages,
                currentPage: this.model.get('page') - 1,
                startPage: paginationConfig.startPage,
                endPage: paginationConfig.endPage,
                pageCount: paginationConfig.pageCount,
                rowRange: [10, 25, 50, 100],
                limit: this.model.get("limit"),
                pageNumLabel: _.template(gettext("Page <%-num%>")),
                isPreviewEnv: user.environment === constants.PREVIEW_APP_ENVIRONMENT,
            };
        },
    });

    return function (options) {
        return new SessionListView(options);
    };
});
