import $ from "jquery";
import constants from "cloudcare/js/formplayer/constants";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import Views from "cloudcare/js/formplayer/sessions/views";
import "cloudcare/js/formplayer/sessions/api";  // for sessions

export default {
    listSessions: function listSessions(pageNumber, pageSize) {
        /* eslint-disable */
        if (pageSize == null) {
            pageSize = parseInt($.cookie("sessions-per-page-limit")) || constants.DEFAULT_INCOMPLETE_FORMS_PAGE_SIZE;
        }
        /* eslint-disable */
        if (pageNumber == null) {
            pageNumber = 0;
        }
        var fetchingSessions = FormplayerFrontend.getChannel().request("sessions", pageNumber, pageSize);

        $.when(fetchingSessions).done(function (sessions) {
            var totalPages = Math.max(1, Math.ceil(sessions.totalSessions / pageSize));
            var sessionListView = Views({
                collection: sessions,
                pageNumber: pageNumber,
                pageSize: pageSize,
                totalPages: totalPages,
                listSessions: listSessions
            });

            FormplayerFrontend.regions.getRegion('main').show(sessionListView);
        });
    },
};
