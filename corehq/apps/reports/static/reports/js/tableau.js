hqDefine("report/js/tableau", [
    'jquery',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/layout',
], function (
    $,
    _,
    initialPageData,
    layout
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
            width: layout.getAvailableContentWidth() + "px",
            height: layout.getAvailableContentHeight() + "px",
        };

        var viz = new tableau.Viz(containerDiv, url, options);
    };

    $(document).ready(function() {
        self.initViz();
        $(window).resize(_.debounce(self.initViz, 300));
    });

    return 1;
});
