/* global tableau */
hqDefine("reports/js/tableau", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        self = {}
        self.errorMessage = ko.observable();

    self.requestViz = function () {
        $.ajax({
            method: 'post',
            url: initialPageData.reverse('tableau_visualisation_ajax'),
            data: {
                validate_hostname: initialPageData.get("validate_hostname"),
                server_name: initialPageData.get("server_address"),
                target_site: initialPageData.get("target_site"),
                domain_username: initialPageData.get("domain_username"),
            },
            dataType: 'json',
            success: function (data) {
                var loadingDiv = document.getElementById("loadingDiv");
                loadingDiv.style.display = "none";
                if (data.success) {
                    self.initViz(data.ticket);
                } else {
                    document.getElementById( 'errorMessage' ).innerHTML = '<b>' + data.message + '</b>';
                }
            },
        }).fail(function () {
            self.errorMessage(gettext("We are sorry, but something unexpected has occurred."));
        });
    }

    self.initViz = function (ticket) {
        var containerDiv = document.getElementById("vizContainer");
        var url = _.template("https://<%- validate_hostname %>/<% if (is_server) { %>trusted/<%- ticket %>/<% } %><%- view_url %>")({
            validate_hostname: initialPageData.get("validate_hostname"),
            is_server: initialPageData.get("server_type") === "server",
            ticket: ticket,
            view_url: initialPageData.get("view_url"),
        });

        new tableau.Viz(containerDiv, url, {
            hideTabs: true,
        });
    };

    $(document).ready(function () {
        self.requestViz();
    });

    return 1;
});
