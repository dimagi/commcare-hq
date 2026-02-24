import Collections from "cloudcare/js/formplayer/users/collections";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import models from "cloudcare/js/formplayer/users/models";
import views from "cloudcare/js/formplayer/users/views";

export default {
    listUsers: function (page, query) {
        var currentUser = models.getCurrentUser(),
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
