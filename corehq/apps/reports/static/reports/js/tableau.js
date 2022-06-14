hqDefine("reports/js/tableau", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        self = {};

    self.initViz = function() {
        var containerDiv = document.getElementById("vizContainer");
        var url = _.template("https://<%- validate_hostname %>/<% if (is_server) { %>trusted/<%- ticket %>/<% } %><%- view_url %>")({
            validate_hostname: initialPageData.get("validate_hostname"),
            is_server: initialPageData.get("server_type") === "server",
            ticket: initialPageData.get("ticket"),
            view_url: initialPageData.get("view_url"),
        });

        new tableau.Viz(containerDiv, url, {
            hideTabs: true,
        });
    };

    $(document).ready(function() {
        self.initViz();
    });

    return 1;
});
