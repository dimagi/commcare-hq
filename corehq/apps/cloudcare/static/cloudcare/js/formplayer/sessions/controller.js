/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.SessionList", function (SessionList, FormplayerFrontend, Backbone, Marionette, $) {
    SessionList.Controller = {
        listSessions: function () {
            var fetchingSessions = FormplayerFrontend.request("sessions");

            $.when(fetchingSessions).done(function (sessions) {

                var sessionListView = new SessionList.SessionListView({
                    collection: sessions,
                });

                FormplayerFrontend.regions.getRegion('main').show(sessionListView);
            });
        },
    };
});