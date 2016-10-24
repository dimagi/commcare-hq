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
    });
});

