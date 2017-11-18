hqDefine("dashboard/js/dashboard", function() {
    var TileModel = function(options) {
        var self = _.extend({}, options);

        self.hasItemList = self.pagination && self.pagination.pages;

        return self;
    };

    var DashboardModel = function(options) {
        var self = this;
        self.tiles = _.map(options.tiles, function(t) { return new TileModel(t); });

        return self;
    };

    $(function() {
        $("#dashboard-tiles").koApplyBindings(new DashboardModel({
            tiles: hqImport("hqwebapp/js/initial_page_data").get("dashboard_tiles"),
        }));

        // Set up popovers
        // TODO: need to initialize these every time there's a new page (report titles have popovers)
        $(".panel-dashboard [data-popover]").each(function() {
            var $target = $(this),
                data = $target.data();
            $target.popover({
                title: data.popoverTitle,
                content: data.popover,
                placement: data.popoverPlacement || "top",
                trigger: 'hover',
            });
        });

        // TODO: Initial fetch for paginated tiles
    });
});
