hqDefine("dashboard/js/dashboard", function() {
    var TileModel = function(options) {
        var self = this;
        self.title = options.title;
        self.slug = options.slug;
        self.icon = options.icon;
        self.url = options.url;
        self.helpText = options.help_text;
        self.hasError = ko.observable(false);

        self.hasItemList = options.pagination && options.pagination.pages;
        if (self.hasItemList) {
            self.itemsPerPage = options.pagination.items_per_page;
            self.pages = options.pagination.pages;
            self.currentPage = 1;
            self.items = ko.observableArray();

            // Fetch first page of data
            $.ajax({
                method: "GET",
                url: hqImport('hqwebapp/js/initial_page_data').reverse('dashboard_tile', self.slug),
                data: {
                    itemsPerPage: self.itemsPerPage,
                    currentPage: self.currentPage,
                },
                success: function(data) {
                    self.items(data.items);
                },
                error: function() {
                    self.hasError(true);
                },
            });
        }

        self.showBackgroundIcon = ko.computed(function() {
            return self.hasItemList && !self.hasError();
        });

        self.showSpinner = ko.computed(function() {
            return self.hasItemList && self.items().length === 0 && !self.hasError();
        });

        self.showItemList = ko.computed(function() {
            return !self.showSpinner() && !self.hasError();
        });

        self.showIconLink = ko.computed(function() {
            return !self.hasItemList || self.hasError();
        });

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
    });
});
