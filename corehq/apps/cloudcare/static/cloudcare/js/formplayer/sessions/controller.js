/*global FormplayerFrontend */

hqDefine("cloudcare/js/formplayer/sessions/controller", function () {
    return {
        listSessions: function () {
            var fetchingSessions = FormplayerFrontend.getChannel().request("sessions");

            $.when(fetchingSessions).done(function (sessions) {

                var sessionListView = hqImport("cloudcare/js/formplayer/sessions/views")({
                    collection: sessions,
                });

                FormplayerFrontend.regions.getRegion('main').show(sessionListView);
            });
        },
    };
});