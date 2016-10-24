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
            this.total = options.total;
            this.page = 1;
        },
        ui: {
            next: '.js-user-next',
            prev: '.js-user-previous',
        },
        events: {
            'click @ui.next': 'onClickNext',
            'click @ui.prev': 'onClickPrev',
        },
        templateHelpers: function() {
            return {
                page: this.page,
                total: this.total,
                totalPages: Math.ceil(this.total / this.limit)
            };
        },
        onClickNext: function(e) {
            console.log('Next');
        },
        onClickPrev: function(e) {
            console.log('Prev');
        },
    });
});

