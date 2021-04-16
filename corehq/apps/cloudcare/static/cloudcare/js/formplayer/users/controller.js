hqDefine("cloudcare/js/formplayer/users/controller", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");
    return {
        listUsers: function (page, query) {
            var currentUser = FormplayerFrontend.getChannel().request('currentUser'),
                users;

            users = hqImport("cloudcare/js/formplayer/users/collections")([], { domain: currentUser.domain });
            var restoreAsView = hqImport("cloudcare/js/formplayer/users/views").RestoreAsView({
                collection: users,
                page: page,
                query: query,
            });

            FormplayerFrontend.regions.getRegion('main').show(restoreAsView);
        },
    };
});
