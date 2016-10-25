/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.Users", function(Users, FormplayerFrontend, Backbone, Marionette, $){
    Users.Views = {}
    Users.Views.UserRowView = Marionette.ItemView.extend({
        template: '#user-row-view-template',
        className: 'formplayer-request',
        tagName: 'tr',
    });
    Users.Views.RestoreAsView = Marionette.CompositeView.extend({
        childView: Users.Views.UserRowView,
        childViewContainer: 'tbody',
        template: '#restore-as-view-template',
        limit: 10,
        initialize: function(options) {
            this.model = new Backbone.Model({
                page: 1,
                query: '',
            });
            this.model.on('change', this.fetchUsers.bind(this));
        },
        ui: {
            next: '.js-user-next',
            prev: '.js-user-previous',
            search: '.js-user-search',
            query: '.js-user-query',
            page: '.js-page',
        },
        events: {
            'click @ui.next': 'onClickNext',
            'click @ui.prev': 'onClickPrev',
            'click @ui.page': 'onClickPage',
            'submit @ui.search': 'onSubmitUserSearch',
        },
        templateHelpers: function() {
            return {
                total: this.collection.total,
                totalPages: this.totalPages(),
            };
        },
        totalPages: function() {
            return Math.ceil(this.collection.total / this.limit);
        },
        fetchUsers: function() {
            this.collection.fetch({
                reset: true,
                data: JSON.stringify({
                    query: this.model.get('query'),
                    limit: this.limit,
                    page: this.model.get('page'),
                })
            }).done(this.render.bind(this));
        },
        onClickNext: function(e) {
            e.preventDefault();
            if (this.model.get('page') === this.totalPages()) {
                console.warn('Attempted to non existant page');
                return;
            }
            this.model.set('page', this.model.get('page') + 1);
        },
        onClickPrev: function(e) {
            e.preventDefault();
            if (this.model.get('page') === 1) {
                console.warn('Attempted to non existant page');
                return;
            }
            this.model.set('page', this.model.get('page') - 1);
        },
        onClickPage: function(e) {
            e.preventDefault();
            var page = $(e.currentTarget).data().page;
            this.model.set('page', page);
        },
        onSubmitUserSearch: function(e) {
            e.preventDefault();
            this.model.set('query', this.ui.query.val());
        },
    });
});

