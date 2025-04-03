hqDefine("reports/js/tableau", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'commcarehq',
], function (
    $,
    _,
    initialPageData,
) {
    var self = {};

    self.requestViz = function () {
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
        var containerDiv = document.getElementById("vizContainer");
        var url = _.template("https://<%- validate_hostname %>/<% if (is_server) { %>trusted/<%- ticket %>/<% } %><%- view_url %>")({
            validate_hostname: initialPageData.get("validate_hostname"),
            is_server: initialPageData.get("server_type") === "server",
            ticket: ticket,
            view_url: initialPageData.get("view_url"),
        });

        $.getScript("https://" + initialPageData.get("validate_hostname") + "/javascripts/api/tableau-2.5.0.min.js", function () {
            new window.tableau.Viz(containerDiv, url, {
                hideTabs: true,
            });
        });
    };

    $(document).ready(function () {
        self.requestViz();
    });

    return 1;
});
