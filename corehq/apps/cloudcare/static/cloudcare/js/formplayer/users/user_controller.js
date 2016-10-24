/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.Users", function(Users, FormplayerFrontend, Backbone, Marionette, $){
    Users.Controller = {
        listUsers: function(){
            var currentUser = FormplayerFrontend.request('currentUser'),
                users;

            users = new FormplayerFrontend.Collections.User({ domain: currentUser.domain }),
            users.fetch().done(function(responseObject) {
                var restoreAsView = new Users.Views.RestoreAsView({
                    collection: users,
                    total: responseObject.response.total,
                });

                FormplayerFrontend.regions.main.show(restoreAsView);
            });
        },
    };
});

