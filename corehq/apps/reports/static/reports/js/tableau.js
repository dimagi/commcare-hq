hqDefine("report/js/tableau", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
    initialPageData
) {
    var self = {};

    self.initViz = function() {
        var containerDiv = document.getElementById("vizContainer");
        var url = _.template("https://<%- validate_hostname %>/<% if (is_server) { %>trusted/<%- ticket %>/<% } %><%- view_url %>")({
            validate_hostname: initialPageData.get("validate_hostname"),
            is_server: initialPageData.get("server_type") === "server",
            ticket: initialPageData.get("ticket"),
            view_url: initialPageData.get("view_url"),
        });

        var options = {
            hideTabs: true,
            width: "800px",
            height: "700px",
        };

        var viz = new tableau.Viz(containerDiv, url, options);
    };

    $(document).ready(function() {
        self.initViz();
    });

    return 1;
});
