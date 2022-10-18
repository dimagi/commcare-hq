hqDefine("cloudcare/js/formplayer/users/controller", function () {
    var Collections = hqImport("cloudcare/js/formplayer/users/collections"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Views = hqImport("cloudcare/js/formplayer/users/views");

    return {
        listUsers: function (page, query) {
            var currentUser = FormplayerFrontend.getChannel().request('currentUser'),
                users;

            users = Collections([], { domain: currentUser.domain });
            var restoreAsView = Views.RestoreAsView({
                collection: users,
                page: page,
                query: query,
            });

            FormplayerFrontend.trigger('clearProgress');
            FormplayerFrontend.regions.getRegion('main').show(restoreAsView);
        },
    };
});
