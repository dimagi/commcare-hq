'use strict';
hqDefine("cloudcare/js/formplayer/users/controller", [
    'cloudcare/js/formplayer/users/collections',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/users/views'
], function (
    Collections,
    FormplayerFrontend,
    views
) {
    return {
        listUsers: function (page, query) {
            var currentUser = FormplayerFrontend.getChannel().request('currentUser'),
                users;

            users = Collections([], { domain: currentUser.domain });
            var restoreAsView = views.RestoreAsView({
                collection: users,
                page: page,
                query: query,
            });

            FormplayerFrontend.trigger('clearProgress');
            FormplayerFrontend.regions.getRegion('main').show(restoreAsView);
        },
    };
});
