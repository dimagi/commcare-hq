/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.Users", function(Users, FormplayerFrontend, Backbone, Marionette){
    Users.Controller = {
        listUsers: function(page, query){
            var currentUser = FormplayerFrontend.request('currentUser'),
                users;

            users = new FormplayerFrontend.Collections.User([], { domain: currentUser.domain });
            var restoreAsView = new Users.Views.RestoreAsView({
                collection: users,
                page: page,
                query: query,
            });

            FormplayerFrontend.regions.main.show(restoreAsView);
        },
    };
});
