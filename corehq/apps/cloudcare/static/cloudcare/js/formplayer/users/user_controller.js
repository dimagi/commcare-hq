/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.Users", function(Users, FormplayerFrontend, Backbone, Marionette, $){
    Users.Controller = {
        listUsers: function(){
            var currentUser = FormplayerFrontend.request('currentUser'),
                users;

            users = new FormplayerFrontend.Collections.User({ domain: currentUser.domain }),
            users.fetch().done(function() {
                var restoreAsView = new Users.Views.RestoreAsView({
                    collection: users,
                });

                FormplayerFrontend.regions.main.show(restoreAsView);
            });
        },
    };
});

