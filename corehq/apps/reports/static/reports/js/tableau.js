import "commcarehq";
import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";

var self = {};

self.requestViz = function () {
    if (!initialPageData.get("has_connected_app")) {
        // No Connected App configured (e.g. Tableau Public): embed the view URL
        // directly without an auth token.
        $('#loadingDiv').addClass("hide");
        self.initViz(null);
        return;
    }
    $.ajax({
        method: 'post',
        url: initialPageData.reverse('get_tableau_server_ticket'),
        data: {
            viz_id: initialPageData.get("viz_id"),
        },
        dataType: 'json',
        success: function (data) {
            $('#loadingDiv').addClass("hide");
            if (data.success) {
                self.initViz(data.ticket);
            } else {
                $('#errorMessage').removeClass("hide");
                document.getElementById('errorMessage').innerHTML = '<b>' + data.message + '</b>';
            }
        },
        error: function () {
            $('#loadingDiv').addClass("hide");
            var requestErrorMessage = gettext("An error occured with the tableau server request, please ensure " +
                "the server configuration is correct and try again.");
            $('#errorMessage').removeClass("hide");
            document.getElementById("errorMessage").innerHTML = requestErrorMessage;
        },
    });
};

self.initViz = function (ticket) {
    var url = _.template("https://<%- validate_hostname %>/<% if (is_server) { %>trusted/<%- ticket %>/<% } %><%- view_url %>")({
        validate_hostname: initialPageData.get("validate_hostname"),
        is_server: initialPageData.get("server_type") === "server",
        ticket: ticket,
        view_url: initialPageData.get("view_url"),
    });
    // The tableau.embedding script will register a tableau-viz element type
    customElements.whenDefined("tableau-viz").then(function () {
        var viz = document.createElement("tableau-viz");
        viz.setAttribute("src", url);
        viz.setAttribute("toolbar", "hidden");
        viz.setAttribute("hide-tabs", "");
        document.getElementById("vizContainer").appendChild(viz);
    });
};

// POC (DATA-2719): open the report in Tableau web authoring in a new tab,
// reusing the trusted ticket. Tableau enforces edit permissions on its end.
self.openAuthoring = function () {
    // Open the tab synchronously (within the click gesture) so it isn't blocked
    // as a popup, then point it at the authoring URL once we have a ticket.
    var authoringTab = window.open("", "_blank");
    $.ajax({
        method: 'post',
        url: initialPageData.reverse('get_tableau_server_ticket'),
        data: {
            viz_id: initialPageData.get("viz_id"),
        },
        dataType: 'json',
        success: function (data) {
            if (data.success) {
                var authoringPath = initialPageData.get("view_url")
                    .split('?')[0]
                    .replace(/(^|\/)views\//, '$1authoring/');
                authoringTab.location = "https://" + initialPageData.get("validate_hostname") +
                    "/trusted/" + data.ticket + "/" + authoringPath;
            } else {
                authoringTab.close();
                $('#errorMessage').removeClass("hide");
                document.getElementById('errorMessage').innerHTML = '<b>' + data.message + '</b>';
            }
        },
        error: function () {
            authoringTab.close();
        },
    });
};

$(document).ready(function () {
    self.requestViz();
    $('#editInTableau').click(self.openAuthoring);
});
