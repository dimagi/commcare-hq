/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.SessionList", function(SessionList, FormplayerFrontend, Backbone, Marionette, $){
    SessionList.Controller = {
        listSessions: function(){
            var fetchingSessions = FormplayerFrontend.request("sessions");

            $.when(fetchingSessions).done(function (sessions) {

                var sessionListView = new SessionList.SessionListView({
                    collection: sessions,
                });

                FormplayerFrontend.regions.main.show(sessionListView);
            });
        },

        startForm: function(sessionId){
            debugger;
            var fetchingForm = FormplayerFrontend.request("getIncompleteForm", sessionId);
            $.when(fetchingForm).done(function (response) {
                FormplayerFrontend.request('startForm', response, this.app_id);
            });

        },
    };
});