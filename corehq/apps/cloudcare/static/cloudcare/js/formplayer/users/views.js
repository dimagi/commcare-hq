define("cloudcare/js/formplayer/users/views", [
    'jquery',
    'underscore',
    'backbone',
    'backbone.marionette',
    'hqwebapp/js/toggles',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/utils/utils',
    'cloudcare/js/formplayer/users/models',
    'cloudcare/js/formplayer/users/utils',
], function (
    $,
    _,
    Backbone,
    Marionette,
    toggles,
    FormplayerFrontend,
    formplayerUtils,
    usersModels,
    usersUtils,
) {
    /**
     * RestoreAsBanner
     *
     * This View represents the banner that indicates what user your are
     * currently logged in (or restoring) as.
     */
    var RestoreAsBanner = Marionette.View.extend({
        ui: {
            clear: '.js-clear-user',
        },
        events: {
            'click @ui.clear': 'onClickClearUser',
        },
        getTemplate: function () {
            if (this.model.restoreAs) {
                const templateId = this.options.smallScreen || usersModels.getCurrentUser().isAppPreview ?
                    "#restore-as-banner-template" :
                    "#restore-as-pill-template";
                return _.template($(templateId).html() || "");
            } else {
                return _.template("");
            }
        },
        templateContext: function () {
            var template = "";
            if (toggles.toggleEnabled('WEB_APPS_DOMAIN_BANNER')) {
                template = gettext("Working as <b><%- restoreAs %></b> in <b><%- domain %></b>.");
            } else {
                template = gettext("Working as <b><%- restoreAs %></b>.");
            }
            template += " <a class='js-clear-user'>" + gettext("Use <%- username %>.") + "</a>";
            return {
                message: _.template(template)({
                    restoreAs: this.model.restoreAs,
                    username: this.model.getDisplayUsername(),
                    domain: usersModels.getCurrentUser().domain,
                }),
            };
        },
        onClickClearUser: function () {
            FormplayerFrontend.trigger('clearRestoreAsUser');
        },
    });

    /**
     * UserRowView
     *
     * Represents a single row in the Log In As User list
     */
    var UserRowView = Marionette.View.extend({
        template: _.template($("#user-row-view-template").html() || ""),
        className: 'formplayer-request js-user',
        tagName: 'tr',
        events: {
            'click': 'onClickUser',
            'keydown': 'onKeyActionUser',
        },
        attributes: function () {
            return {
                "role": "link",
                "tabindex": "0",
                "aria-label": this.model.get('username'),
            };
        },
        onClickUser: function () {
            formplayerUtils.confirmationModal({
                title: _.template(gettext('Log in as <%- username %>?'))({username: this.model.get('username')}),
                message: _.template($('#user-data-template').html())(
                    { user: this.model.toJSON() },
                ),
                confirmText: gettext('Log in'),
                onConfirm: function () {
                    usersUtils.Users.logInAsUser(this.model.get('username'));
                    FormplayerFrontend.showRestoreAs(usersModels.getCurrentUser());
                    var loginAsNextOptions = FormplayerFrontend.getChannel().request('getLoginAsNextOptions');
                    if (loginAsNextOptions) {
                        FormplayerFrontend.trigger("clearLoginAsNextOptions");
                        import("cloudcare/js/formplayer/menus/controller").then(function (MenusController) {
                            MenusController.selectMenu(loginAsNextOptions);
                        });
                    } else {
                        FormplayerFrontend.trigger('navigateHome');
                    }
                }.bind(this),
            });
        },
        onKeyActionUser: function (e) {
            if (e.keyCode === 13) {
                this.onClickUser();
            }
        },
    });

    /**
     * RestoreAsView
     *
     * Renders all possible users to log in as. Equipped with pagination
     * and custom querying.
     */
    var RestoreAsView = Marionette.CollectionView.extend({
        childView: UserRowView,
        childViewContainer: 'tbody',
        template: _.template($("#restore-as-view-template").html() || ""),
        limit: parseInt($.cookie("users-per-page-limit")) || 10,
        maxPagesShown: 10,
        initialize: function (options) {
            this.model = new Backbone.Model({
                page: options.page || 1,
                query: options.query || '',
            });
            this.model.on('change', function () {
                this.fetchUsers();
                this.navigate();
            }.bind(this));
            this.fetchUsers();
        },
        ui: {
            search: '.js-user-search',
            query: '.js-user-query',
            page: '.js-page',
            paginationGoButton: '#pagination-go-button',
            paginationGoText: '#goText',
            paginationGoTextBox: '.module-go-container',
            usersPerPageLimit: '.per-page-limit',
        },
        events: {
            'click @ui.page': 'onClickPage',
            'submit @ui.search': 'onSubmitUserSearch',
            'click @ui.paginationGoButton': 'paginationGoAction',
            'change @ui.usersPerPageLimit': 'onPerPageLimitChange',
            'keypress @ui.page': 'paginateKeyAction',
            'keypress @ui.paginationGoTextBox': 'paginationGoKeyAction',
        },
        templateContext: function () {
            const paginationOptions = formplayerUtils.paginateOptions(
                this.model.get('page') - 1,
                this.totalPages(),
                this.collection.total,
            );
            return _.extend(paginationOptions, {
                isAppPreview: usersModels.getCurrentUser().isAppPreview,
                total: this.collection.total,
                totalPages: this.totalPages(),
                limit: this.limit,
                currentPage: this.model.get('page') - 1,
            });
        },
        navigate: function () {
            formplayerUtils.navigate(
                '/restore_as/' +
                this.model.get('page') + '/' +
                this.model.get('query'),
            );
        },
        totalPages: function () {
            return Math.ceil(this.collection.total / this.limit);
        },
        fetchUsers: function () {
            this.collection.fetch({
                reset: true,
                data: {
                    query: this.model.get('query'),
                    limit: this.limit,
                    page: this.model.get('page'),
                },
            })
                .done(this.render.bind(this))
                .fail(function (xhr) {
                    FormplayerFrontend.trigger('showError', xhr.responseText);
                });
        },
        onClickPage: function (e) {
            e.preventDefault();
            var page = $(e.currentTarget).data().id;
            this.model.set('page', page + 1);
        },
        paginateKeyAction: function (e) {
            // Pressing Enter on a pagination control activates it.
            if (event.which === 13 || event.keyCode === 13) {
                this.onClickPage(e);
            }
        },
        onSubmitUserSearch: function (e) {
            e.preventDefault();
            this.model.set({
                'query': this.ui.query.val(),
                'page': 1,  // Reset page to one when doing a query
            });
        },
        paginationGoAction: function (e) {
            e.preventDefault();
            var page = Number(this.ui.paginationGoText.val());
            var pageNo = formplayerUtils.paginationGoPageNumber(page, this.totalPages());
            this.model.set('page', pageNo);
        },
        paginationGoKeyAction: function (e) {
            // Pressing Enter in the go box activates it.
            if (event.which === 13 || event.keyCode === 13) {
                this.paginationGoAction(e);
            }
        },
        onPerPageLimitChange: function (e) {
            e.preventDefault();
            var rowCount = this.ui.usersPerPageLimit.val();
            this.limit = Number(rowCount);
            this.fetchUsers();
            this.model.set('page', 1);
            formplayerUtils.savePerPageLimitCookie('users', this.limit);
        },
    });

    return {
        RestoreAsBanner: function (options) {
            return new RestoreAsBanner(options);
        },
        RestoreAsView: function (options) {
            return new RestoreAsView(options);
        },
    };
});

